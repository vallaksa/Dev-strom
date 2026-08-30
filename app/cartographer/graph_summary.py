"""Compact ProjectGraph serialization for LLM prompts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.cartographer.model import ProjectGraph


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
