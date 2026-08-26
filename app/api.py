"""Dev-Strom FastAPI server.

Exposes endpoints for idea generation, expansion, export, and history.
All runs are persisted to PostgreSQL. Until auth is implemented, all
operations use the ANONYMOUS_USER_ID.
"""

import logging

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from app.models.dto import (
    AdviseRequest,
    AnalyzeRequest,
    CartographRequest,
    ExpandRequest,
    ExportRequest,
    IdeasRequest,
)

load_dotenv()

from app.config import settings
from app.graph import app as graph_app, expand_idea as graph_expand_idea
from app.services import db
from app.services.export_formatter import idea_to_markdown
from app.services.run_service import (
    get_latest_expansion,
    get_run,
    load_history,
    save_expanded_idea,
    save_run,
)

# ── Project Cartographer (F1) ────────────────────────────────────────────────
# Persistence is selected by CARTOGRAPH_STORE_BACKEND via get_cartograph_store()
# (postgres JSONB by default, neo4j when configured). Guard ImportError so
# app.api still loads if the cartographer package is missing; routes return
# 503 when these are None.
try:
    from app.cartographer.analyze import analyze_architecture
    from app.cartographer.pipeline import cartograph
    from app.cartographer.store import get_cartograph_store

    _cartograph_store = get_cartograph_store()
    save_cartograph_run = _cartograph_store.save
    get_cartograph_run = _cartograph_store.get
except ImportError as exc:
    logging.getLogger(__name__).error("Cartographer modules failed to import: %s", exc)
    analyze_architecture = None
    cartograph = None
    get_cartograph_run = None
    save_cartograph_run = None

# ── Improvement / Feature Advisor (F2) ───────────────────────────────────────
# Same guarding rationale as the Cartographer import above: keep app.api
# importable (and its routes 503-able) even if app.advisor fails to import
# for some reason, and let tests monkeypatch these names directly.
try:
    from app.advisor.pipeline import advise_repo_with_context
    from app.advisor.store import PostgresJsonbStore as AdvisorPostgresJsonbStore

    _advisor_store = AdvisorPostgresJsonbStore()
    save_advisor_run = _advisor_store.save
    get_advisor_run = _advisor_store.get
except ImportError as exc:
    logging.getLogger(__name__).error("Advisor modules failed to import: %s", exc)
    advise_repo_with_context = None
    get_advisor_run = None
    save_advisor_run = None

# ── Repository Intelligence / Analysis (Evidence-First) ──────────────────────
# Same guarding rationale as the Cartographer/Advisor imports above: keep
# app.api importable (and the /analyze routes 503-able) even if the analyzer
# pipeline/store fails to import, and let tests monkeypatch these names.
try:
    from app.cartographer.analysis_store import PostgresJsonbStore as AnalysisPostgresJsonbStore
    from app.cartographer.pipeline import analyze_repository_with_graph

    _analysis_store = AnalysisPostgresJsonbStore()
    save_analysis_run = _analysis_store.save
    get_analysis_run = _analysis_store.get
except ImportError as exc:
    logging.getLogger(__name__).error("Analyzer modules failed to import: %s", exc)
    analyze_repository_with_graph = None
    get_analysis_run = None
    save_analysis_run = None

# ── Async Job Runner (F4) ────────────────────────────────────────────────────
# Same guarding rationale as the Cartographer/Advisor imports above: keep
# app.api importable (and its async routes 503-able) even if
# app.services.jobs isn't available yet.
try:
    from app.services.jobs import create_job, get_job, run_job
except ImportError as exc:
    logging.getLogger(__name__).error("Job runner module failed to import: %s", exc)
    create_job = None
    get_job = None
    run_job = None

# ── logging ───────────────────────────────────────────────────────────────────
# Configure the root logger once, at app startup, with the level from typed
# config (LOG_LEVEL env var, default INFO). All module-level loggers across
# the app (e.g. app.graph's) inherit this configuration.
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

api = FastAPI(title="Dev-Strom")


# ── Idea Generation ───────────────────────────────────────────────────────────

@api.post("/ideas")
def post_ideas(body: IdeasRequest):
    """Generate project ideas and persist the run to the database."""
    if not settings.openai_api_key or not settings.tavily_api_key:
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY and TAVILY_API_KEY in .env",
        )

    inputs = {"tech_stack": body.tech_stack, "count": body.count}
    if body.domain and body.domain.strip():
        inputs["domain"] = body.domain.strip()
    if body.level and body.level.strip():
        inputs["level"] = body.level.strip()
    if body.enable_multi_query:
        inputs["enable_multi_query"] = True

    result = graph_app.invoke(inputs)
    ideas = result.get("ideas", [])

    # The graph already pads short results with empty ideas (see
    # app.graph.generate_ideas), so a count mismatch here is benign: the
    # model occasionally over- or under-generates. Never 500 for this —
    # truncate if we got too many, and keep whatever we got if we got too
    # few (the caller can retry expand/export against fewer pids).
    if len(ideas) > body.count:
        logger.warning(
            "Model returned %d ideas, requested %d; truncating.", len(ideas), body.count
        )
        ideas = ideas[: body.count]
    elif len(ideas) < body.count:
        logger.warning(
            "Model returned %d ideas, requested %d; keeping what came back.",
            len(ideas), body.count,
        )

    # Attach 1-based position IDs
    out = []
    for i, idea in enumerate(ideas, 1):
        d = idea if isinstance(idea, dict) else (
            idea.model_dump() if hasattr(idea, "model_dump") else {}
        )
        d["pid"] = i
        out.append(d)

    # Persist run to database
    run_id = save_run(
        tech_stack=body.tech_stack,
        domain=inputs.get("domain"),
        level=inputs.get("level"),
        count=body.count,
        enable_multi_query=body.enable_multi_query,
        ideas=out,
        web_context=result.get("web_context"),
    )

    return {"ideas": out, "run_id": run_id}


# ── Idea Expansion ────────────────────────────────────────────────────────────

@api.post("/expand")
def post_expand(body: ExpandRequest):
    """Expand a single idea into a deeper implementation plan."""
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in .env",
        )

    # Load run from database
    run = get_run(run_id=body.run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run {body.run_id} not found.",
        )

    ideas = run["ideas"]
    if body.pid < 1 or body.pid > len(ideas):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pid. Use pid 1–{len(ideas)} for this run.",
        )

    idea = ideas[body.pid - 1].copy()
    idea.pop("pid", None)
    result = graph_expand_idea(idea)

    # Persist expanded idea to database
    save_expanded_idea(
        run_id=body.run_id,
        pid=body.pid,
        extended_plan=result.get("extended_plan", []),
    )

    return result


# ── Export ─────────────────────────────────────────────────────────────────────

@api.post("/export")
def post_export(body: ExportRequest):
    """Export an expanded idea as a downloadable Markdown file."""
    run = get_run(run_id=body.run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run {body.run_id} not found.",
        )

    ideas = run["ideas"]
    if body.pid < 1 or body.pid > len(ideas):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pid. Use pid 1–{len(ideas)} for this run.",
        )

    idea = ideas[body.pid - 1].copy()
    idea.pop("pid", None)

    # Reuse the expansion already persisted by POST /expand for this
    # (run_id, pid), if one exists — don't call the LLM again. Only expand
    # on-demand (and persist the result, same as POST /expand) when this
    # idea has never been expanded, so callers don't have to call
    # POST /expand first.
    latest = get_latest_expansion(run_id=body.run_id, pid=body.pid)
    if latest is not None:
        extended_plan = latest["extended_plan"]
    else:
        logger.info(
            "No persisted expansion for run_id=%s pid=%s; expanding on demand.",
            body.run_id, body.pid,
        )
        expanded = graph_expand_idea(idea)
        extended_plan = expanded.get("extended_plan", [])
        save_expanded_idea(
            run_id=body.run_id,
            pid=body.pid,
            extended_plan=extended_plan,
        )

    md = idea_to_markdown(idea, extended_plan, run.get("tech_stack"))
    name_slug = (idea.get("name") or "idea").replace(" ", "_")[:50]
    filename = f"devstrom_{name_slug}.md"

    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── History ────────────────────────────────────────────────────────────────────

@api.get("/history")
def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="Max runs to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """Return the user's past runs, most recent first."""
    runs = load_history(limit=limit, offset=offset)
    return {"runs": runs, "limit": limit, "offset": offset}


@api.get("/runs/{run_id}")
def get_run_detail(run_id: str):
    """Return full details of a single run including all ideas."""
    run = get_run(run_id=run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found.",
        )
    return run


# ── Project Cartographer (F1) ────────────────────────────────────────────────

def _to_dict(obj) -> dict:
    """Normalize a ProjectGraph/ArchitectureReport (real pydantic model, or a
    dict/mock in tests) into a plain, JSON-serializable dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)


def _run_cartograph_pipeline(target: str, repo_url: str | None) -> dict:
    """Run the cartograph+analyze pipeline and persist the result. Shared by
    the sync and async paths of POST /cartograph — returns the same dict
    shape that is the sync path's 200 response body.
    """
    project_graph = cartograph(target, repo_url=repo_url)
    architecture_report = analyze_architecture(project_graph)
    run_id = save_cartograph_run(project_graph, architecture_report)
    return {
        "run_id": run_id,
        "project_graph": _to_dict(project_graph),
        "architecture_report": _to_dict(architecture_report),
    }


@api.post("/cartograph")
def post_cartograph(
    body: CartographRequest,
    background_tasks: BackgroundTasks,
    async_: bool = Query(False, alias="async"),
):
    """Map a repository's architecture: build a ProjectGraph, analyze it into
    an ArchitectureReport, persist both, and return them.

    By default this runs synchronously — the clone/parse/analyze pipeline
    runs inline on the request, same as always. Pass `?async=true` to
    instead schedule the pipeline as a background job and get back
    `{job_id, status}` immediately (202); poll GET /jobs/{job_id} for the
    result.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in .env",
        )
    if cartograph is None or analyze_architecture is None or save_cartograph_run is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cartographer core modules (app.cartographer.pipeline/analyze/store) "
                "are not available yet."
            ),
        )

    target = body.repo_url or body.path

    if async_:
        if create_job is None or run_job is None:
            raise HTTPException(
                status_code=503,
                detail="Job runner module (app.services.jobs) is not available yet.",
            )
        job_id = create_job(kind="cartograph", params=body.model_dump())
        background_tasks.add_task(run_job, job_id, lambda: _run_cartograph_pipeline(target, body.repo_url))
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "pending"})

    try:
        return _run_cartograph_pipeline(target, body.repo_url)
    except Exception as exc:
        logger.exception("Cartograph pipeline failed for %r", target)
        raise HTTPException(
            status_code=500,
            detail=f"Cartograph failed: {exc}",
        ) from exc


@api.get("/cartograph/{run_id}")
def get_cartograph_run_detail(run_id: str):
    """Return a previously persisted cartograph run: {run_id, project_graph,
    architecture_report}. 404 if it does not exist.
    """
    if get_cartograph_run is None:
        raise HTTPException(
            status_code=503,
            detail="Cartographer core modules (app.cartographer.store) are not available yet.",
        )

    record = get_cartograph_run(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cartograph run {run_id} not found.",
        )
    return record


# ── Improvement / Feature Advisor (F2) ───────────────────────────────────────

def _run_advise_pipeline(repo_url: str | None, path: str | None, run_id_param: str | None) -> dict:
    """Run the advisor pipeline and persist the result. Shared by the sync
    and async paths of POST /advise — returns the same dict shape that is
    the sync path's 200 response body.
    """
    result = advise_repo_with_context(
        url_or_path=repo_url or path,
        run_id=run_id_param,
    )
    run_id = save_advisor_run(
        result["advisor_report"],
        cartograph_run_id=result["cartograph_run_id"],
        repo_url=result["repo_url"],
    )
    return {
        "run_id": run_id,
        "advisor_report": _to_dict(result["advisor_report"]),
    }


@api.post("/advise")
def post_advise(
    body: AdviseRequest,
    background_tasks: BackgroundTasks,
    async_: bool = Query(False, alias="async"),
):
    """Produce a prioritized improvement roadmap for a repository, grounded in
    its actual code graph: either map+analyze it fresh (repo_url/path) or
    advise against an existing cartograph run (run_id). Persists and returns
    the resulting AdvisorReport.

    By default this runs synchronously, same as POST /cartograph. Pass
    `?async=true` to instead schedule the pipeline as a background job and
    get back `{job_id, status}` immediately (202); poll GET /jobs/{job_id}
    for the result.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Set OPENAI_API_KEY in .env",
        )
    if advise_repo_with_context is None or save_advisor_run is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Advisor core modules (app.advisor.pipeline/advise/store) "
                "are not available yet."
            ),
        )

    if async_:
        if create_job is None or run_job is None:
            raise HTTPException(
                status_code=503,
                detail="Job runner module (app.services.jobs) is not available yet.",
            )
        job_id = create_job(kind="advise", params=body.model_dump())
        background_tasks.add_task(
            run_job,
            job_id,
            lambda: _run_advise_pipeline(body.repo_url, body.path, body.run_id),
        )
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "pending"})

    try:
        return _run_advise_pipeline(body.repo_url, body.path, body.run_id)
    except Exception as exc:
        logger.exception(
            "Advisor pipeline failed for repo_url=%r path=%r run_id=%r",
            body.repo_url, body.path, body.run_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Advisor pipeline failed: {exc}",
        ) from exc


@api.get("/advise/{run_id}")
def get_advise_run_detail(run_id: str):
    """Return a previously persisted advisor run: {run_id, cartograph_run_id,
    repo_url, advisor_report, created_at}. 404 if it does not exist.
    """
    if get_advisor_run is None:
        raise HTTPException(
            status_code=503,
            detail="Advisor core modules (app.advisor.store) are not available yet.",
        )

    record = get_advisor_run(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Advisor run {run_id} not found.",
        )
    return record


# ── Repository Intelligence / Analysis (Evidence-First) ──────────────────────

def _analysis_response(run_id: str, analysis: dict, graph: dict | None) -> dict:
    """The flat /analyze response body: the domain Analysis at top level (its
    `mermaid` architecture diagram included, may be null), plus the persisted
    `run_id` (used by GET /analyze/{run_id}) and the `graph` extra (the
    structural ProjectGraph, for a UI that renders the wiring natively)."""
    return {"run_id": run_id, **analysis, "graph": graph}


def _run_analyze_pipeline(target: str, repo_url: str | None) -> dict:
    """Run the evidence-first analysis pipeline and persist the result. Shared
    by the sync and async paths of POST /analyze — returns the same dict shape
    that is the sync path's 200 response body."""
    analysis, project_graph = analyze_repository_with_graph(target, repo_url=repo_url)
    graph_dict = _to_dict(project_graph)
    run_id = save_analysis_run(analysis, project_graph=graph_dict, repo_url=repo_url)
    return _analysis_response(run_id, _to_dict(analysis), graph_dict)


@api.post("/analyze")
def post_analyze(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    async_: bool = Query(False, alias="async"),
):
    """Produce an evidence-first Repository Intelligence Analysis: ingest the
    repo deterministically, run the analysis, and return the domain `Analysis`
    (Repository + Findings + Recommendations) plus the structural `graph`.

    Runs synchronously by default, same as POST /cartograph. Pass
    `?async=true` to schedule it as a background job and get back
    `{job_id, status}` immediately (202); poll GET /jobs/{job_id}.
    """
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Set OPENAI_API_KEY in .env")
    if analyze_repository_with_graph is None or save_analysis_run is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Analyzer core modules (app.cartographer.pipeline/analysis_store) "
                "are not available yet."
            ),
        )

    target = body.repo_url or body.path

    if async_:
        if create_job is None or run_job is None:
            raise HTTPException(
                status_code=503,
                detail="Job runner module (app.services.jobs) is not available yet.",
            )
        job_id = create_job(kind="analyze", params=body.model_dump())
        background_tasks.add_task(run_job, job_id, lambda: _run_analyze_pipeline(target, body.repo_url))
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "pending"})

    try:
        return _run_analyze_pipeline(target, body.repo_url)
    except Exception as exc:
        logger.exception("Analyze pipeline failed for %r", target)
        raise HTTPException(status_code=500, detail=f"Analyze failed: {exc}") from exc


@api.get("/analyze/{run_id}")
def get_analyze_run_detail(run_id: str):
    """Return a previously persisted analysis run in the same flat shape as
    POST /analyze (Analysis fields + `graph` + `mermaid`), so the UI's History
    can reload a past run. 404 if it does not exist.
    """
    if get_analysis_run is None:
        raise HTTPException(
            status_code=503,
            detail="Analyzer core modules (app.cartographer.analysis_store) are not available yet.",
        )

    record = get_analysis_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Analysis run {run_id} not found.")
    return _analysis_response(record["run_id"], record["analysis"], record.get("project_graph"))


# ── Async Jobs (F4) ───────────────────────────────────────────────────────────

@api.get("/jobs/{job_id}")
def get_job_detail(job_id: str):
    """Return the status/result of a background job scheduled via
    `?async=true` on POST /cartograph or POST /advise: {job_id, kind,
    status, params, result, error, created_at, updated_at}. 404 if it does
    not exist.
    """
    if get_job is None:
        raise HTTPException(
            status_code=503,
            detail="Job runner module (app.services.jobs) is not available yet.",
        )

    record = get_job(job_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found.",
        )
    return record


# ── Health / Readiness ───────────────────────────────────────────────────────

@api.get("/health")
def health():
    """Liveness probe: the process is up and can serve requests.

    Always returns 200 — does not check downstream dependencies (DB, LLM
    providers). Use /ready for that.
    """
    return {"status": "ok"}


@api.get("/ready")
def ready():
    """Readiness probe: the process is up AND its dependencies are usable.

    Pings the database if DATABASE_URL is configured. If no database is
    configured, that's a valid (DB-less) deployment, so this reports ok
    rather than failing.
    """
    if not settings.database_url:
        return {"status": "ok", "database": "not configured"}

    try:
        db.ping()
    except Exception as exc:
        logger.error("Readiness check failed: database unreachable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database unreachable: {exc}",
        )

    return {"status": "ok", "database": "reachable"}
