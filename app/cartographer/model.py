"""Shared data contract for repository intelligence ingestion.

These pydantic models are THE contract between the deterministic parser
(ingest + parse -> ProjectGraph) and the evidence-first analysis layer.
Both sides import from this module — do not duplicate or fork these
definitions elsewhere.

Field shapes are deliberately permissive (lots of `dict` / `list[dict]`)
because the two producers (deterministic parser vs. LLM) fill them
differently; validation of *content* (e.g. mermaid syntax) is left to
whichever side produces it.
"""

from typing import Literal

from pydantic import BaseModel, Field

# ── Node ─────────────────────────────────────────────────────────────────────

NodeType = Literal[
    "repo",
    "package",
    "module",
    "file",
    "class",
    "function",
    "external_dep",
    "service",
    "entrypoint",
]


class Node(BaseModel):
    """One vertex in the ProjectGraph.

    `id` must be stable and globally unique within a graph, e.g.
    "module:app/graph.py", "class:app/graph.py:MyClass", or
    "ext:langgraph" for an external dependency. Callers should be able to
    recompute the same id for the same logical entity across re-parses.
    """

    id: str
    type: NodeType
    label: str
    path: str | None = None
    language: str | None = None
    summary: str | None = None
    meta: dict = Field(default_factory=dict)


# ── Edge ─────────────────────────────────────────────────────────────────────

EdgeType = Literal[
    "contains",
    "imports",
    "calls",
    "depends_on",
    "exposes",
    "reads_writes",
]


class Edge(BaseModel):
    """One directed relationship between two Node ids."""

    source: str
    target: str
    type: EdgeType
    meta: dict = Field(default_factory=dict)


# ── ProjectGraph ─────────────────────────────────────────────────────────────


class ProjectGraph(BaseModel):
    """The normalized structural graph produced by parse.build_project_graph.

    This is the deterministic, parser-derived half of the contract. The
    evidence-first `Analysis` (findings + recommendations) is derived FROM
    a ProjectGraph but is stored/returned separately via the analysis store.
    """

    repo_url: str | None = None
    root_path: str
    languages: list[str] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    manifests: dict = Field(default_factory=dict)
    stats: dict = Field(default_factory=dict)
