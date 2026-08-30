"""Orchestration entry points for repository intelligence:

    analyze_repository:           url_or_path -> resolve/clone -> parse -> Repository
                                  -> evidence-first Analysis (Repository + Findings +
                                     Recommendations)
    analyze_repository_with_graph: same, but also returns the structural ProjectGraph
"""

import logging
from pathlib import Path

from app.cartographer.aggregate import to_system_graph
from app.cartographer.findings import analyze_findings
from app.cartographer.ingest import (
    _git_commit_sha,
    cleanup_clone,
    repository_from_graph,
    resolve_source,
)
from app.cartographer.model import ProjectGraph
from app.cartographer.parse import build_project_graph
from app.models.domain import Analysis

logger = logging.getLogger(__name__)


def _ingest_and_analyze(
    url_or_path: str, repo_url: str | None, depth: int
) -> tuple[Analysis, ProjectGraph]:
    """Clone/parse ONCE and derive both the `Analysis` and the structural
    `ProjectGraph` from that single parse. Shared body of the two public
    entry points below."""
    logger.info("analyze_repository: resolving source %r", url_or_path)
    was_local_dir = Path(url_or_path).expanduser().is_dir()
    provenance = repo_url or (None if was_local_dir else url_or_path)
    root_path = resolve_source(url_or_path, depth=depth)

    try:
        commit_sha = _git_commit_sha(root_path)
        full_graph = build_project_graph(root_path, repo_url=provenance, include_members=False)
        repository = repository_from_graph(full_graph, commit_sha=commit_sha)
        graph = to_system_graph(full_graph)
    finally:
        if not was_local_dir:
            cleanup_clone(root_path)

    analysis = analyze_findings(graph, repository)
    logger.info(
        "analyze_repository: %s -> %d findings, %d recommendations (status=%s)",
        repository.id, len(analysis.findings), len(analysis.recommendations), analysis.status,
    )
    return analysis, graph


def analyze_repository(url_or_path: str, repo_url: str | None = None, depth: int = 1) -> Analysis:
    """Resolve `url_or_path`, ingest it into a `Repository`, and run the
    evidence-first analysis, returning a single `Analysis` (Repository +
    Findings + Recommendations).

    Clones/parses exactly once: the same `ProjectGraph` feeds both the
    deterministic `Repository` (via `repository_from_graph`) and the LLM
    findings pass (via `analyze_findings`). Temporary clones are cleaned up
    before returning (success or failure); caller-supplied local directories
    are never touched.

    Use `analyze_repository_with_graph` instead if you also need the raw
    structural `ProjectGraph` (e.g. to render an architecture visualization).

    Args:
        url_or_path: git URL or existing local directory.
        repo_url: provenance recorded on the graph/Repository. Defaults to
            `url_or_path` when it is a URL (not an existing local dir).
        depth: shallow-clone depth for URL sources; ignored for local dirs.
    """
    analysis, _graph = _ingest_and_analyze(url_or_path, repo_url, depth)
    return analysis


def analyze_repository_with_graph(
    url_or_path: str, repo_url: str | None = None, depth: int = 1
) -> tuple[Analysis, ProjectGraph]:
    """Like `analyze_repository`, but also returns the structural
    `ProjectGraph` produced during ingestion.

    The graph carries the deterministic node/edge structure an architecture
    visualization needs; the API layer surfaces it alongside the `Analysis`
    so a UI can render both the evidence-first findings and the wiring
    diagram from a single call — without a second clone/parse.
    """
    return _ingest_and_analyze(url_or_path, repo_url, depth)
