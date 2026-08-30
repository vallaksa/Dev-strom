"""Orchestration entry point for the Improvement / Feature Advisor (F2):

    (url_or_path | run_id) -> ProjectGraph [+ ArchitectureReport] -> AdvisorReport

Two entry paths, exactly one of which must be supplied by the caller:
  - `run_id`: load an EXISTING analysis or cartograph run (its ProjectGraph
    and, if it has one, its ArchitectureReport) and advise against that —
    no re-clone/re-parse/re-analyze. Analysis runs (what Cartographer saves
    today) are tried first; cartograph_runs is the fallback.
  - `url_or_path`: run the full F1 pipeline fresh (`cartograph` then
    `analyze_architecture`), then advise against the freshly built graph.

Persistence of the resulting AdvisorReport itself is NOT wired in here -
that's `app.advisor.store` / integration (API) code's job, same division of
responsibility as `app.cartographer.pipeline` vs `app.cartographer.store`.
"""

import logging

from app.advisor.advise import advise
from app.advisor.model import AdvisorReport
from app.cartographer.analyze import analyze_architecture
from app.cartographer.model import ArchitectureReport, ProjectGraph
from app.cartographer.pipeline import cartograph
from app.services.db import get_session
from app.services.models import CartographRun
from app.services.slugs import get_by_public_id

logger = logging.getLogger(__name__)


def _load_from_run(run_id: str) -> tuple[ProjectGraph, ArchitectureReport | None, str | None]:
    """Load a previously persisted analysis or cartograph run.

    Returns (graph, architecture_report, cartograph_row_uuid_or_none).
    Analysis-sourced loads leave the cartograph UUID as None.
    """
    from app.cartographer.analysis_store import PostgresJsonbStore as AnalysisStore

    analysis_record = AnalysisStore().get(run_id)
    if analysis_record is not None:
        graph = analysis_record.get("project_graph")
        if not graph:
            raise ValueError(f"Analysis run {run_id} has no project graph to advise against.")
        return ProjectGraph.model_validate(graph), None, None

    with get_session() as session:
        row = get_by_public_id(session, CartographRun, run_id)
        if row is None:
            raise ValueError(f"Run {run_id} not found.")
        project_graph = ProjectGraph.model_validate(row.project_graph)
        architecture_report = (
            ArchitectureReport.model_validate(row.architecture_report)
            if row.architecture_report
            else None
        )
        return project_graph, architecture_report, str(row.id)


def advise_repo_with_context(url_or_path: str | None = None, run_id: str | None = None) -> dict:
    """Like `advise_repo`, but also returns the metadata the API layer needs
    to persist the resulting AdvisorReport (see app.advisor.store /
    AdvisorRun) without re-deriving it: the source cartograph run id (when
    one was loaded/used) and the repo_url provenance of the graph advised
    against.

    Returns: {"advisor_report": AdvisorReport, "cartograph_run_id": str | None,
    "repo_url": str | None}.
    """
    if run_id:
        logger.info("advise_repo: loading existing run %r", run_id)
        project_graph, architecture_report, cartograph_run_id = _load_from_run(run_id)
    elif url_or_path:
        logger.info("advise_repo: running cartograph pipeline fresh for %r", url_or_path)
        project_graph = cartograph(url_or_path)
        architecture_report = analyze_architecture(project_graph)
        cartograph_run_id = None  # fresh pipeline run isn't itself persisted to cartograph_runs here
    else:
        raise ValueError("advise_repo requires exactly one of url_or_path or run_id.")

    report = advise(project_graph, architecture_report)
    return {
        "advisor_report": report,
        "cartograph_run_id": cartograph_run_id,
        "repo_url": project_graph.repo_url,
    }


def advise_repo(url_or_path: str | None = None, run_id: str | None = None) -> AdvisorReport:
    """Produce an AdvisorReport for a repo, either by loading an existing
    cartograph run (`run_id`) or by running the F1 pipeline fresh
    (`url_or_path`). Exactly one of the two must be provided - callers
    (typically the API's DTO validator) are responsible for enforcing that;
    this function itself just prefers `run_id` when both happen to be set.

    Thin wrapper around `advise_repo_with_context` for callers that only
    want the report itself (e.g. direct/unit-test use).
    """
    return advise_repo_with_context(url_or_path=url_or_path, run_id=run_id)["advisor_report"]
