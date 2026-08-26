"""Orchestration entry points for Project Cartographer:

    cartograph:          url_or_path -> resolve/clone -> parse -> ProjectGraph
    analyze_repository:   url_or_path -> resolve/clone -> parse -> Repository
                          -> evidence-first Analysis (Repository + Findings +
                             Recommendations)

`cartograph` remains the low-level "just give me the ProjectGraph" entry point
(persistence via CartographStore, and the free-form ArchitectureReport via
app.cartographer.analyze, are wired in by the API layer). `analyze_repository`
is the higher-level, domain-model-shaped pipeline from the Product Evolution
Plan: it clones/parses once and derives BOTH the deterministic Repository and
the evidence-first Analysis from that single ProjectGraph.
"""

import logging
from pathlib import Path

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


def cartograph(url_or_path: str, repo_url: str | None = None, depth: int = 1) -> ProjectGraph:
    """Resolve `url_or_path` (git URL or local directory) and parse it into
    a ProjectGraph.

    Args:
        url_or_path: a git URL (http/https/git/ssh, or scp-like
            `git@host:path`) or an existing local directory.
        repo_url: recorded on the resulting ProjectGraph as its provenance.
            Defaults to `url_or_path` itself when that looks like a URL
            (i.e. it wasn't resolved from an existing local directory).
        depth: shallow-clone depth, passed through to `resolve_source` when
            `url_or_path` is a URL. Ignored for local directories.

    Returns:
        The parsed ProjectGraph. Temporary clones created for this call are
        cleaned up before returning (whether parsing succeeds or fails);
        caller-supplied local directories are never touched.
    """
    logger.info("cartograph: resolving source %r", url_or_path)
    # Mirrors resolve_source's own local-vs-URL decision, so provenance and
    # cleanup agree with what it actually did (cleanup_clone is additionally
    # guarded by its own tempdir-prefix check, so this is belt-and-braces,
    # not the only thing standing between us and deleting a real repo).
    was_local_dir = Path(url_or_path).expanduser().is_dir()
    root_path = resolve_source(url_or_path, depth=depth)

    try:
        graph = build_project_graph(root_path, repo_url=repo_url or (None if was_local_dir else url_or_path))
    finally:
        if not was_local_dir:
            cleanup_clone(root_path)

    return graph


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
        graph = build_project_graph(root_path, repo_url=provenance)
    finally:
        if not was_local_dir:
            cleanup_clone(root_path)

    repository = repository_from_graph(graph, commit_sha=commit_sha)
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
    visualization needs (the same shape `POST /cartograph` returns as
    `project_graph`); the API layer surfaces it alongside the `Analysis` so a
    UI can render both the evidence-first findings and the wiring diagram from
    a single call — without a second clone/parse.
    """
    return _ingest_and_analyze(url_or_path, repo_url, depth)
