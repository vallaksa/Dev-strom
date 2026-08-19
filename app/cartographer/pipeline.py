"""Orchestration entry point for Project Cartographer's core pipeline:

    url_or_path -> resolve/clone -> parse -> ProjectGraph

Analysis (LLM -> ArchitectureReport) and persistence (CartographStore) are
deliberately NOT wired in here - those belong to the companion F1 agent and
to integration code, respectively. This module's only job is to hand back a
ProjectGraph that both sides can rely on.
"""

import logging
from pathlib import Path

from app.cartographer.ingest import cleanup_clone, resolve_source
from app.cartographer.model import ProjectGraph
from app.cartographer.parse import build_project_graph

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
