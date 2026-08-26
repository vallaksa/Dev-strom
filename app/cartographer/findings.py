"""Evidence-First structured analysis: turns a `ProjectGraph` + `Repository`
into an `Analysis` (evidence-backed `Finding`s and the `Recommendation`s
derived from them).

This is the "Evidence-First AI Analysis" layer from the Product Evolution
Plan (§13): every important conclusion the model draws must point back at
concrete repository evidence — a file, a line/range, a symbol — with a short
explanation. Findings that cite nothing are the smell this design exists to
avoid, so the prompt demands evidence and the parser preserves it.

It reuses the same deep-agent + MODEL/MODEL_FALLBACKS + markdown-fence-stripping
machinery as `app.cartographer.analyze` (which produces the free-form
`ArchitectureReport`); this module is the *structured*, domain-model-shaped
counterpart producing `app.models.domain` objects. Like `analyze`, it is
hermetic/mockable: `parse_analysis` never raises, and callers/tests can
monkeypatch `_invoke_with_fallback` to drive the agent's raw output without a
real LLM call.
"""

from __future__ import annotations

import json
import logging
import uuid
from functools import lru_cache
from typing import Any, get_args

from deepagents import create_deep_agent

from app.cartographer.analyze import summarize_graph
from app.config import settings
from app.graph import _extract_last_content, _invoke_with_fallback, _strip_markdown_fences
from app.models.domain import (
    Analysis,
    Evidence,
    Finding,
    FindingCategory,
    ImpactLevel,
    Recommendation,
    RecommendationType,
    Repository,
    Severity,
)

logger = logging.getLogger(__name__)

# ── Model selection (same pattern as app.graph / app.cartographer.analyze) ─────
MODEL = settings.model
MODEL_FALLBACKS = settings.model_fallbacks

# Closed literal sets, for coercing/validating the LLM's free-text enums to a
# safe in-range default rather than dropping a whole finding on a typo.
_VALID_CATEGORIES = frozenset(get_args(FindingCategory))
_VALID_SEVERITIES = frozenset(get_args(Severity))
_VALID_REC_TYPES = frozenset(get_args(RecommendationType))
_VALID_LEVELS = frozenset(get_args(ImpactLevel))  # ImpactLevel == EffortLevel

_DEFAULT_CATEGORY = "architecture"
_DEFAULT_SEVERITY = "info"
_DEFAULT_REC_TYPE = "engineering"
_DEFAULT_LEVEL = "medium"


# ── system prompt ──────────────────────────────────────────────────────────────

_FINDINGS_SYSTEM = """\
You are a senior software architect performing an EVIDENCE-FIRST review of a codebase.
You are given a compact JSON summary of its dependency graph (nodes = files/modules/
classes/functions/services, edges = imports/calls/dependencies), manifests, entrypoints,
and languages.

Your job: produce structured, evidence-backed findings and the recommendations that
follow from them. The single most important rule: DO NOT state a conclusion you cannot
ground in the provided graph. Every finding should cite concrete evidence (a file/path,
a symbol, and ideally a node id from the input) and explain what that evidence shows.
Prefer FEWER, well-grounded findings over many speculative ones.

1. Output MUST be valid JSON in EXACTLY the shape below. No markdown fences, no prose
   before/after, no extra keys:
{
  "summary": "2-4 sentence system overview: what this codebase is and how it is organized.",
  "findings": [
    {
      "category": "architecture | design | scalability | reliability | security | performance | maintainability | testing | product",
      "title": "Short, specific finding title.",
      "description": "What you observed and why it matters, grounded in the evidence below.",
      "confidence": 0.0-1.0,
      "severity": "critical | high | medium | low | info",
      "evidence": [
        {
          "file": "repo/relative/path.py",
          "symbol": "ClassName.method or module name (optional)",
          "explanation": "What THIS specific code shows that supports the finding."
        }
      ]
    }
  ],
  "recommendations": [
    {
      "finding_ref": 0,
      "type": "product | engineering | scalability | reliability | security | developer_experience",
      "title": "Actionable recommendation title.",
      "description": "Concrete change to make.",
      "impact": "high | medium | low",
      "effort": "high | medium | low",
      "priority": 1
    }
  ]
}

2. CONTENT GUIDELINES:
   - "findings": Ground each in real nodes/paths/manifests from the input. Use the file
     paths and symbols that actually appear in the graph. Set "confidence" honestly —
     lower it when the graph only weakly supports the claim.
   - "evidence": At least one entry per finding wherever the graph permits. "explanation"
     is REQUIRED on every evidence entry; "file"/"symbol" are optional but strongly
     preferred. Do NOT invent files or symbols that are not in the input.
   - "recommendations": Each SHOULD map to a finding via "finding_ref" — the 0-based index
     of the finding in the "findings" array it addresses. Omit "finding_ref" only for a
     genuinely cross-cutting recommendation. "priority" is a 1-based rank (1 = do first).
   - Split recommendations by "type" as the plan intends (product / engineering / scalability
     / reliability / security / developer_experience), not everything as "engineering".

3. STRICT GUARDRAILS:
   - NO markdown, code blocks, comments, or text outside the single JSON object.
   - Do NOT use any tools or external APIs.
   - Base every claim on the provided graph/manifests/entrypoints; never fabricate files,
     symbols, components, or integrations with no evidence in the input.
   - If you cannot comply, output exactly:
     {"summary": "", "findings": [], "recommendations": []}
"""


# ── agent singleton (created once per model, reused) ──────────────────────────

@lru_cache(maxsize=None)
def _get_findings_agent(model: str = MODEL):
    return create_deep_agent(
        name="evidence_first_analyst",
        model=model,
        tools=[],
        system_prompt=_FINDINGS_SYSTEM,
    )


# ── coercion helpers ───────────────────────────────────────────────────────────

def _coerce_literal(value: Any, valid: frozenset[str], default: str) -> str:
    """Map an LLM-supplied enum string to an in-range literal, defaulting when
    it is missing or out of set (so one bad enum never drops a whole item)."""
    if isinstance(value, str) and value.strip().lower() in valid:
        return value.strip().lower()
    return default


def _coerce_confidence(value: Any) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(1.0, max(0.0, c))


def _coerce_evidence(raw: Any) -> list[Evidence]:
    """Build Evidence items from the LLM's list. `explanation` is required; an
    evidence entry without one is skipped rather than fabricated."""
    out: list[Evidence] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        explanation = item.get("explanation")
        if not (isinstance(explanation, str) and explanation.strip()):
            continue
        out.append(
            Evidence(
                file=item.get("file") or None,
                line_start=_opt_pos_int(item.get("line_start")),
                line_end=_opt_pos_int(item.get("line_end")),
                symbol=item.get("symbol") or None,
                snippet=item.get("snippet") or None,
                explanation=explanation.strip(),
            )
        )
    return out


def _opt_pos_int(value: Any) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 1 else None


def _coerce_findings(raw: Any, repository_id: str) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(raw, list):
        return findings
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not (isinstance(title, str) and title.strip()):
            continue  # a finding with no title carries no signal
        evidence = _coerce_evidence(item.get("evidence"))
        if not evidence:
            # Evidence-First: keep it (so nothing is silently lost) but flag it.
            logger.warning("Finding %r has no citable evidence; keeping but flagging.", title)
        findings.append(
            Finding(
                id=f"finding-{i + 1}",
                repository_id=repository_id,
                category=_coerce_literal(item.get("category"), _VALID_CATEGORIES, _DEFAULT_CATEGORY),
                title=title.strip(),
                description=(item.get("description") or "").strip(),
                evidence=evidence,
                confidence=_coerce_confidence(item.get("confidence")),
                severity=_coerce_literal(item.get("severity"), _VALID_SEVERITIES, _DEFAULT_SEVERITY),
            )
        )
    return findings


def _coerce_recommendations(raw: Any, finding_ids: list[str]) -> list[Recommendation]:
    """Build Recommendations, resolving each `finding_ref` (0-based index into
    the findings array) to the corresponding finding id. An out-of-range or
    missing ref yields a cross-cutting recommendation (finding_id=None)."""
    recs: list[Recommendation] = []
    if not isinstance(raw, list):
        return recs
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not (isinstance(title, str) and title.strip()):
            continue
        ref = item.get("finding_ref")
        finding_id: str | None = None
        if isinstance(ref, int) and 0 <= ref < len(finding_ids):
            finding_id = finding_ids[ref]
        recs.append(
            Recommendation(
                id=f"rec-{i + 1}",
                finding_id=finding_id,
                type=_coerce_literal(item.get("type"), _VALID_REC_TYPES, _DEFAULT_REC_TYPE),
                title=title.strip(),
                description=(item.get("description") or "").strip(),
                impact=_coerce_literal(item.get("impact"), _VALID_LEVELS, _DEFAULT_LEVEL),
                effort=_coerce_literal(item.get("effort"), _VALID_LEVELS, _DEFAULT_LEVEL),
                priority=_opt_pos_int(item.get("priority")) or (i + 1),
            )
        )
    return recs


# ── parsing / assembly ─────────────────────────────────────────────────────────

def _minimal_analysis(repository: Repository, note: str) -> Analysis:
    """Always-valid Analysis used when the agent's output can't be produced or
    parsed. Marked failed, with the reason surfaced in the summary rather than
    swallowed — so callers can distinguish 'no issues' from 'analysis broke'."""
    return Analysis(
        id=str(uuid.uuid4()),
        repository=repository,
        summary=note,
        findings=[],
        recommendations=[],
        status="failed",
    )


def parse_analysis(raw: str, repository: Repository) -> Analysis:
    """Parse an agent's raw text into a validated `Analysis`, grounding every
    finding in `repository`. Strips markdown fences first; on any failure
    returns a `_minimal_analysis` (status="failed") — never raises.

    `repository_id` on findings is always set from `repository` here (never
    trusted from the model), keeping the evidence chain authoritative.
    """
    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("top-level analysis JSON must be an object")
    except Exception as exc:
        logger.warning("Failed to parse Analysis JSON: %s", exc)
        return _minimal_analysis(repository, f"Analysis output could not be parsed: {exc}")

    findings = _coerce_findings(data.get("findings"), repository.id)
    recommendations = _coerce_recommendations(data.get("recommendations"), [f.id for f in findings])
    summary = data.get("summary")
    return Analysis(
        id=str(uuid.uuid4()),
        repository=repository,
        summary=summary.strip() if isinstance(summary, str) else "",
        findings=findings,
        recommendations=recommendations,
        status="complete",
    )


# ── public entry point ──────────────────────────────────────────────────────────

def analyze_findings(graph: Any, repository: Repository) -> Analysis:
    """Run the evidence-first analyst over `graph` and return a validated
    `Analysis` grounded in `repository`.

    Hermetic/mockable: monkeypatch this function directly, or monkeypatch
    `_get_findings_agent` / `_invoke_with_fallback` to control the agent's raw
    output without a real LLM call. Any agent-invocation failure degrades to a
    failed `_minimal_analysis` rather than propagating.
    """
    summary_json = summarize_graph(graph)
    user_content = (
        "ProjectGraph (compact JSON summary):\n"
        f"{summary_json}\n\n"
        "Return the evidence-first Analysis JSON now."
    )

    try:
        result = _invoke_with_fallback(
            _get_findings_agent, [{"role": "user", "content": user_content}]
        )
    except Exception as exc:
        logger.error("analyze_findings: agent invocation failed: %s", exc)
        return _minimal_analysis(repository, f"Analysis failed: {exc}")

    raw = _extract_last_content(result)
    return parse_analysis(raw, repository)
