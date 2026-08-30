"""Architecture analysis: turns a `ProjectGraph` into an `ArchitectureReport`.

This module is part of "Project Cartographer" (F1). It depends on
`app.cartographer.model` (the `ProjectGraph` / `ArchitectureReport` pydantic
contract) which is owned by a parallel branch (feat/f1-core) building
`app/cartographer/{model,ingest,parse,store,pipeline}.py`. That module does
not exist yet in this worktree, so it is imported lazily (inside
`analyze_architecture`, guarded by try/except) rather than at module import
time — this keeps `app.cartographer.analyze` importable, and its JSON
parsing unit-testable, before feat/f1-core lands. At integration this becomes
a normal import once `app/cartographer/model.py` exists.

Everything else here follows the same shape as the idea-generation agent in
`app.graph`: a `create_deep_agent` singleton (cached per model), invoked
through the same MODEL -> MODEL_FALLBACKS chain, with the same markdown-fence
stripping before JSON parsing.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent

from app.config import settings
from app.graph import _extract_last_content, _invoke_with_fallback, _strip_markdown_fences
from app.llm import chat_model

if TYPE_CHECKING:  # pragma: no cover - typing only, module may not exist yet
    from app.cartographer.model import ArchitectureReport, ProjectGraph

logger = logging.getLogger(__name__)

# ── Model selection (same pattern as app.graph) ───────────────────────────────
MODEL = settings.model
MODEL_FALLBACKS = settings.model_fallbacks


# ── system prompt ──────────────────────────────────────────────────────────────

_ANALYZE_SYSTEM = """\
You are a distributed-systems architect. You are given a SYSTEM-LEVEL graph of a
codebase: services/bounded contexts, external integrations, datastores, and
entrypoints — NOT individual classes or functions. Your job is to explain how the
system is organized and which architecture patterns it exhibits.

1. Output MUST be valid JSON, using ONLY the exact shape below. Do NOT include
   markdown code fences, explanations, headings, or any extra text.
2. Use THIS JSON shape, and nothing else:
{
  "summary": "2-4 sentence overview at the distributed-systems level: major services, data flow, and primary pattern (monolith, modular monolith, BFF, etc.).",
  "components": [
    {
      "name": "Service or bounded context name",
      "responsibility": "One sentence on what this part of the system does in production.",
      "node_ids": ["id-of-a-node-in-the-input-graph", "..."]
    }
  ],
  "layers": ["Client", "API", "Domain", "Data", "..."],
  "data_flow": "1-3 sentences describing request/data flow between services and stores.",
  "external_integrations": ["Postgres", "OpenAI API", "..."],
  "mermaid": "flowchart TD\\n  A[Web] --> B[API]\\n  B --> C[(Database)]\\n  ...",
  "risks": ["System-level risk or gap", "..."],
  "design_decisions": [
    {
      "title": "Architecture pattern or decision (e.g. Modular monolith, Sync HTTP API)",
      "why": "Why the system appears structured this way.",
      "benefits": ["What this pattern buys"],
      "tradeoffs": ["What it costs at scale or operability"],
      "alternatives": ["Plausible alternative pattern"]
    }
  ]
}

3. CONTENT GUIDELINES:
   - Think in SERVICES and PATTERNS — never describe individual classes/functions.
   - "components": 3-8 logical services/bounded contexts mapped to input `service:*` nodes.
   - "design_decisions": Name recognizable architecture patterns (layered, hexagonal,
     event-driven, BFF, modular monolith, etc.) evidenced by the graph — not code trivia.
   - "mermaid": Service/integration diagram only (≤15 nodes). Use datastore shapes for DBs.
   - Use `stats.architecture_patterns` from the input when present as hints.

4. STRICT GUARDRAILS:
   - NO markdown, code blocks, or text outside the JSON object.
   - Do NOT invent services or integrations absent from the input graph.
   - If you cannot comply, output exactly:
     {"summary": "", "components": [], "layers": [], "data_flow": "", "external_integrations": [], "mermaid": "", "risks": [], "design_decisions": []}
"""


# ── agent singleton (created once per model, reused) ──────────────────────────

@lru_cache(maxsize=None)
def _get_analyze_agent(model: str = MODEL):
    return create_deep_agent(
        name="architecture_analyst",
        model=chat_model(model),
        tools=[],
        system_prompt=_ANALYZE_SYSTEM,
    )


# ── compact ProjectGraph serialization ─────────────────────────────────────────

def _field(obj: Any, key: str, default: Any = None) -> Any:
    """Read `key` off `obj`, whether it's a pydantic model, a dict, or a mock."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def summarize_graph(graph: "ProjectGraph", *, max_nodes: int = 80, max_edges: int = 150) -> str:
    """Serialize a ProjectGraph into a compact JSON string within a token budget.

    Keeps: languages, entrypoints, manifests, stats, and a capped slice of
    nodes/edges (id/type/label/path/language + a truncated summary) rather
    than the full graph, to keep the agent's input small and cheap.
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


# ── JSON parsing / validation ──────────────────────────────────────────────────

_EMPTY_REPORT_KWARGS: dict = {
    "summary": "",
    "components": [],
    "layers": [],
    "data_flow": "",
    "external_integrations": [],
    "mermaid": "",
    "risks": [],
    "design_decisions": [],
}


def _minimal_report(note: str) -> "ArchitectureReport":
    """Build a minimal, always-valid ArchitectureReport (empty mermaid, a risks note)
    for use when the agent's output can't be parsed/validated."""
    from app.cartographer.model import ArchitectureReport  # deferred: see module docstring

    return ArchitectureReport(**{**_EMPTY_REPORT_KWARGS, "risks": [note]})


def parse_architecture_report(raw: str) -> "ArchitectureReport":
    """Parse and validate an agent's raw text response into an ArchitectureReport.

    Strips markdown fences (models sometimes wrap JSON in ```json blocks despite
    instructions), then validates against the real ArchitectureReport pydantic
    model. On any failure, returns a minimal report with an empty mermaid string
    and a risks entry explaining what went wrong — this function never raises.
    """
    from app.cartographer.model import ArchitectureReport  # deferred: see module docstring

    cleaned = _strip_markdown_fences(raw)
    try:
        data = json.loads(cleaned)
        return ArchitectureReport.model_validate(data)
    except Exception as exc:
        logger.warning("Failed to parse/validate ArchitectureReport JSON: %s", exc)
        return _minimal_report(f"Analysis output could not be parsed: {exc}")


# ── public entry point ──────────────────────────────────────────────────────────

def analyze_architecture(graph: "ProjectGraph") -> "ArchitectureReport":
    """Run the architecture-analyst agent over `graph` and return a validated
    ArchitectureReport (including a Mermaid diagram string).

    Hermetic/mockable: callers (and tests) can monkeypatch this function
    directly, or monkeypatch `_get_analyze_agent` / `_invoke_with_fallback`
    to control the agent's raw output without any real LLM call.
    """
    try:
        from app.cartographer.model import ArchitectureReport  # noqa: F401 - see module docstring
    except ImportError as exc:  # pragma: no cover - only hit before feat/f1-core lands
        raise RuntimeError(
            "app.cartographer.model is not available yet (feat/f1-core has not landed "
            "in this worktree)."
        ) from exc

    summary_json = summarize_graph(graph)
    user_content = (
        "ProjectGraph (compact JSON summary):\n"
        f"{summary_json}\n\n"
        "Return the ArchitectureReport JSON now."
    )

    try:
        result = _invoke_with_fallback(
            _get_analyze_agent, [{"role": "user", "content": user_content}]
        )
    except Exception as exc:
        logger.error("analyze_architecture: agent invocation failed: %s", exc)
        return _minimal_report(f"Analysis failed: {exc}")

    raw = _extract_last_content(result)
    return parse_architecture_report(raw)
