"""Improvement / Feature Advisor: turns a `ProjectGraph` (+ optional
`ArchitectureReport`) into a prioritized `AdvisorReport`.

This module is part of F2, and follows the exact same shape as F1's
`app.cartographer.analyze`: a `create_deep_agent` singleton (cached per
model), invoked through the same MODEL -> MODEL_FALLBACKS chain (both
reused directly from `app.graph`), with the same markdown-fence stripping
before JSON parsing.

Unlike `app.cartographer.analyze` (written before F1 had merged into this
worktree), F1 has already merged here - so `app.cartographer.model` and
`app.advisor.model` are imported normally at module scope, not lazily.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from deepagents import create_deep_agent

from app.advisor.model import AdvisorReport
from app.cartographer.model import ArchitectureReport, ProjectGraph
from app.config import settings
from app.graph import _extract_last_content, _invoke_with_fallback, _strip_markdown_fences

logger = logging.getLogger(__name__)

# ── Model selection (same pattern as app.graph / app.cartographer.analyze) ────
MODEL = settings.model
MODEL_FALLBACKS = settings.model_fallbacks


# ── system prompt ──────────────────────────────────────────────────────────────

_ADVISE_SYSTEM = """\
You are a pragmatic staff engineer acting as an Improvement / Feature Advisor. You are
given a compact JSON summary of a codebase's dependency graph (nodes = files/modules/
services, edges = imports/calls/dependencies), its manifests, entrypoints, languages,
and - when available - an existing architecture analysis (summary, components, risks).
Your job is to produce a PRIORITIZED improvement roadmap: next features, refactors,
tech debt, and risks, each grounded in evidence from the input.

1. Output MUST be valid JSON, using ONLY the exact shape below. Do NOT include
   markdown code fences, explanations, headings, or any extra text.
2. Use THIS JSON shape, and nothing else:
{
  "summary": "2-4 sentence overview of the codebase's current state and where it most needs investment.",
  "tech_stack": ["Detected language/framework/library", "..."],
  "recommendations": [
    {
      "id": "short-stable-slug, e.g. rec-1",
      "category": "feature|refactor|tech_debt|risk|test|security|performance|docs",
      "title": "Short, specific, actionable title.",
      "rationale": "1-3 sentences explaining WHY this matters, citing concrete evidence from the graph/report (specific files, missing tests, tight coupling, absent error handling, etc).",
      "impact": "high|medium|low",
      "effort": "high|medium|low",
      "affected_node_ids": ["id-of-a-node-in-the-input-graph", "..."],
      "suggested_steps": ["Concrete next step 1", "Concrete next step 2", "..."]
    }
  ],
  "quick_wins": ["id-or-title of a low-effort/high-value recommendation", "..."],
  "strategic_bets": ["id-or-title of a high-effort/high-value recommendation", "..."]
}

3. CONTENT GUIDELINES:
   - "tech_stack": Only list languages/frameworks/libraries actually evidenced by the
     manifests, node languages, or imports in the input graph. Do not invent tech.
   - "recommendations": Produce 5-12 recommendations spanning multiple categories where
     evidenced (do not force every category if there is no evidence for it). Each
     "affected_node_ids" entry MUST reference an "id" that appears in the input graph's
     nodes; use [] only when a recommendation is genuinely cross-cutting and cannot be
     pinned to specific nodes.
   - "impact"/"effort": Assign realistically based on the scope implied by the affected
     nodes and the nature of the change - do not default everything to "high"/"medium".
   - "suggested_steps": 2-5 concrete, actionable steps a developer could follow.
   - "quick_wins": Recommendations with LOW effort and MEDIUM-or-HIGH impact. Reference
     each by its "id" (preferred) or exact "title" from "recommendations".
   - "strategic_bets": Recommendations with HIGH effort and HIGH impact (larger, riskier
     bets worth planning for). Reference each by its "id" (preferred) or exact "title".
     A recommendation should not appear in both "quick_wins" and "strategic_bets".

4. STRICT GUARDRAILS:
   - NO markdown, code blocks, comments, or text before/after/beside the JSON.
   - Do NOT use any tools or external APIs.
   - Do NOT invent new fields or deviate from the required JSON structure.
   - Base every recommendation on evidence in the provided graph/report; do not fabricate
     files, components, or problems that have no evidence in the input.
   - If you cannot comply with all instructions, output exactly:
     {"summary": "", "tech_stack": [], "recommendations": [], "quick_wins": [], "strategic_bets": []}
"""


# ── agent singleton (created once per model, reused) ──────────────────────────

@lru_cache(maxsize=None)
def _get_advisor_agent(model: str = MODEL):
    return create_deep_agent(
        name="improvement_advisor",
        model=model,
        tools=[],
        system_prompt=_ADVISE_SYSTEM,
    )


# ── compact ProjectGraph / ArchitectureReport serialization ───────────────────

def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read `key` off `obj`, whether it's a pydantic model, a dict, or a mock."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def summarize_graph(graph: "ProjectGraph", *, max_nodes: int = 80, max_edges: int = 150) -> str:
    """Serialize a ProjectGraph into a compact JSON string within a token budget.

    Keeps: languages, entrypoints, manifests, stats, and a capped slice of
    nodes/edges (id/type/label/path/language + a truncated summary) rather
    than the full graph. Mirrors `app.cartographer.analyze.summarize_graph`
    exactly (same caps, same shape) so both agents see a consistent, cheap
    view of the graph.
    """
    nodes = list(_field(graph, "nodes", []) or [])
    edges = list(_field(graph, "edges", []) or [])

    compact_nodes = [
        {
            "id": _field(n, "id"),
            "type": _field(n, "type"),
            "label": _field(n, "label"),
            "path": _field(n, "path"),
            "language": _field(n, "language"),
            "summary": (_field(n, "summary") or "")[:200] or None,
        }
        for n in nodes[:max_nodes]
    ]
    compact_edges = [
        {
            "source": _field(e, "source"),
            "target": _field(e, "target"),
            "type": _field(e, "type"),
        }
        for e in edges[:max_edges]
    ]

    payload = {
        "repo_url": _field(graph, "repo_url"),
        "root_path": _field(graph, "root_path"),
        "languages": _field(graph, "languages", []),
        "entrypoints": _field(graph, "entrypoints", []),
        "manifests": _field(graph, "manifests", {}),
        "stats": _field(graph, "stats", {}),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": compact_nodes,
        "edges": compact_edges,
        "truncated": len(nodes) > max_nodes or len(edges) > max_edges,
    }
    return json.dumps(payload, default=str)


def summarize_architecture_report(report: "ArchitectureReport | None", *, max_risks: int = 10) -> dict | None:
    """Build a compact dict of an ArchitectureReport's summary/components/risks
    for inclusion in the advisor prompt. Returns None if no report is given -
    the advisor still works from the graph alone in that case.
    """
    if report is None:
        return None

    components = list(_field(report, "components", []) or [])
    risks = list(_field(report, "risks", []) or [])

    return {
        "summary": _field(report, "summary", ""),
        "layers": _field(report, "layers", []),
        "data_flow": _field(report, "data_flow", ""),
        "external_integrations": _field(report, "external_integrations", []),
        "components": [
            {
                "name": _field(c, "name"),
                "responsibility": _field(c, "responsibility"),
                "node_ids": _field(c, "node_ids", []),
            }
            for c in components
        ],
        "risks": risks[:max_risks],
    }


# ── JSON parsing / validation ──────────────────────────────────────────────────

_EMPTY_REPORT_KWARGS: dict = {
    "summary": "",
    "tech_stack": [],
    "recommendations": [],
    "quick_wins": [],
    "strategic_bets": [],
}


def _minimal_report(note: str) -> "AdvisorReport":
    """Build a minimal, always-valid AdvisorReport (empty recommendations, a
    single explanatory risk-style recommendation) for use when the agent's
    output can't be parsed/validated."""
    return AdvisorReport(
        **{
            **_EMPTY_REPORT_KWARGS,
            "recommendations": [
                {
                    "id": "rec-error",
                    "category": "risk",
                    "title": "Advisor output could not be generated",
                    "rationale": note,
                    "impact": "low",
                    "effort": "low",
                    "affected_node_ids": [],
                    "suggested_steps": [],
                }
            ],
        }
    )


def parse_advisor_report(raw: str) -> "AdvisorReport":
    """Parse and validate an agent's raw text response into an AdvisorReport.

    Strips markdown fences (models sometimes wrap JSON in ```json blocks
    despite instructions), then validates against the real AdvisorReport
    pydantic model. On any failure, returns a minimal report with a single
    explanatory risk-style recommendation - this function never raises.
    """
    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
        return AdvisorReport.model_validate(data)
    except Exception as exc:
        logger.warning("Failed to parse/validate AdvisorReport JSON: %s", exc)
        return _minimal_report(f"Advisor output could not be parsed: {exc}")


# ── public entry point ──────────────────────────────────────────────────────────

def advise(graph: "ProjectGraph", report: "ArchitectureReport | None" = None) -> "AdvisorReport":
    """Run the improvement-advisor agent over `graph` (and, if available,
    `report`) and return a validated, prioritized AdvisorReport.

    Hermetic/mockable: callers (and tests) can monkeypatch this function
    directly, or monkeypatch `_get_advisor_agent` / `_invoke_with_fallback`
    to control the agent's raw output without any real LLM call.
    """
    graph_summary_json = summarize_graph(graph)
    report_summary = summarize_architecture_report(report)

    parts = [
        "ProjectGraph (compact JSON summary):",
        graph_summary_json,
    ]
    if report_summary is not None:
        parts.append("\nExisting ArchitectureReport (summary/components/risks):")
        parts.append(json.dumps(report_summary, default=str))
    parts.append("\nReturn the AdvisorReport JSON now.")
    user_content = "\n".join(parts)

    try:
        result = _invoke_with_fallback(
            _get_advisor_agent, [{"role": "user", "content": user_content}]
        )
    except Exception as exc:
        logger.error("advise: agent invocation failed: %s", exc)
        return _minimal_report(f"Advisor invocation failed: {exc}")

    raw = _extract_last_content(result)
    return parse_advisor_report(raw)
