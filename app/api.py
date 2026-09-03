"""Dev-Strom FastAPI server.

Exposes endpoints for idea generation, expansion, export, history, and
repository intelligence (POST /analyze). All runs are persisted to PostgreSQL
and scoped to the requesting user. When AUTH_ENABLED is false every request
resolves to the seeded anonymous user (see app.auth).
"""

import asyncio
import logging
import uuid

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from app.models.dto import (
    AnalyzeRequest,
    ExpandRequest,
    ExportRequest,
    IdeasRequest,
)

from app.services.models import ANONYMOUS_USER_ID

load_dotenv()

from app.auth.deps import require_user
from app.auth.routes import router as auth_router
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
    update_run_idea,
)

# ── Repository Intelligence / Analysis (Evidence-First) ──────────────────────
# Guard imports so app.api stays loadable if the analyzer pipeline fails;
# tests monkeypatch these names directly.
try:
    from app.cartographer.analysis_store import PostgresJsonbStore as AnalysisPostgresJsonbStore
    from app.cartographer.pipeline import analyze_repository_with_graph

    _analysis_store = AnalysisPostgresJsonbStore()
    save_analysis_run = _analysis_store.save
    get_analysis_run = _analysis_store.get
    list_analysis_runs = _analysis_store.list_runs
except ImportError as exc:
    logging.getLogger(__name__).error("Analyzer modules failed to import: %s", exc)
    analyze_repository_with_graph = None
    get_analysis_run = None
    save_analysis_run = None
    list_analysis_runs = None

# ── Async Job Runner (F4) ────────────────────────────────────────────────────
# Guard imports so app.api stays loadable if app.services.jobs is unavailable.
try:
    from app.services.jobs import create_job, get_job, get_job_status, run_job
    from app.services.sse import SSE_HEADERS, job_event_stream
except ImportError as exc:
    logging.getLogger(__name__).error("Job runner module failed to import: %s", exc)
    create_job = None
    get_job = None
    get_job_status = None
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
api.include_router(auth_router)


# ── Idea Generation ───────────────────────────────────────────────────────────

def _run_ideas_pipeline(body: IdeasRequest, user_id: uuid.UUID) -> dict:
    """Run the idea-generation pipeline and persist the run under `user_id`.
    Shared by the sync and async paths of POST /ideas — returns the same dict
    shape that is the sync path's 200 response body: {ideas, run_id}.
    """
    intent = body.intent.strip() if body.intent and body.intent.strip() else None
    effective_stack = (body.tech_stack.strip() if body.tech_stack and body.tech_stack.strip() else intent) or ""

    requested_count = 2
    inputs = {"tech_stack": effective_stack, "count": requested_count}
    if intent:
        inputs["intent"] = intent
    if body.domain and body.domain.strip():
        inputs["domain"] = body.domain.strip()
    if body.level and body.level.strip():
        inputs["level"] = body.level.strip()
    if body.refinement_context and body.refinement_context.strip():
        inputs["refinement_context"] = body.refinement_context.strip()
    if body.prior_ideas:
        inputs["prior_ideas"] = [
            {"name": p.name, "problem_statement": p.problem_statement}
            for p in body.prior_ideas
        ]

    result = graph_app.invoke(inputs)
    ideas = result.get("ideas", [])

    if len(ideas) > requested_count:
        logger.warning(
            "Model returned %d ideas, requested %d; truncating.", len(ideas), requested_count
        )
        ideas = ideas[:requested_count]
    elif len(ideas) < requested_count:
        logger.warning(
            "Model returned %d ideas, requested %d; keeping what came back.",
            len(ideas), requested_count,
        )

    out = []
    for i, idea in enumerate(ideas, 1):
        d = idea if isinstance(idea, dict) else (
            idea.model_dump() if hasattr(idea, "model_dump") else {}
        )
        d["pid"] = i
        out.append(d)

    # Persist run to database. Generation already succeeded — a down or
    # misconfigured DB must not 500 away the ideas the caller just paid for.
    try:
        run_id = save_run(
            tech_stack=effective_stack,
            domain=inputs.get("domain"),
            level=inputs.get("level"),
            count=requested_count,
            enable_multi_query=body.enable_multi_query,
            ideas=out,
            web_context=result.get("web_context"),
            user_id=user_id,
        )
    except Exception:
        logger.exception("Failed to persist idea run; returning generated ideas anyway")
        from app.services.slugs import slugify
        run_id = slugify(effective_stack)

    return {"ideas": out, "run_id": run_id}


@api.post("/ideas")
def post_ideas(
    body: IdeasRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_user),
    async_: bool = Query(False, alias="async"),
):
    """Generate project ideas and persist the run to the database.

    Runs synchronously by default (200 with {ideas, run_id}). Pass
    `?async=true` to schedule it as a background job and get back
    {job_id, status: pending} immediately (202); subscribe to
    GET /jobs/{job_id}/events or poll GET /jobs/{job_id}.
    """
    if not settings.api_key:
        raise HTTPException(
            status_code=503,
            detail="Set API_KEY (or OPENROUTER_API_KEY / OPENAI_API_KEY) in .env",
        )

    owner_id = uuid.UUID(user["id"])

    if async_:
        if create_job is None or run_job is None:
            raise HTTPException(
                status_code=503,
                detail="Job runner module (app.services.jobs) is not available yet.",
            )
        try:
            job_id = create_job(
                kind="ideas", params={**body.model_dump(), "user_id": str(owner_id)}
            )
        except Exception:
            # 503, not 500: the UI only falls back to sync POST /ideas on 503.
            # Job-store failures (Postgres down, DATABASE_URL unset, missing
            # jobs table) must not strand generation behind a spinner.
            logger.exception("Failed to create ideas job")
            raise HTTPException(
                status_code=503,
                detail="Job store unavailable; cannot schedule async idea generation.",
            ) from None
        background_tasks.add_task(
            run_job, job_id, lambda: _run_ideas_pipeline(body, owner_id)
        )
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "pending"})

    return _run_ideas_pipeline(body, owner_id)


# ── Idea Expansion ────────────────────────────────────────────────────────────

@api.post("/expand")
def post_expand(body: ExpandRequest, user: dict = Depends(require_user)):
    """Expand a single idea into a deeper implementation plan."""
    if not settings.api_key:
        raise HTTPException(
            status_code=503,
            detail="Set API_KEY in .env",
        )

    # Load run from database (scoped to the caller)
    run = get_run(run_id=body.run_id, owner_id=uuid.UUID(user["id"]))
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

    expanded_idea = result.get("idea", idea)
    update_run_idea(run_id=body.run_id, pid=body.pid, idea=expanded_idea)

    save_expanded_idea(
        run_id=body.run_id,
        pid=body.pid,
        extended_plan=result.get("extended_plan", []),
    )

    return result


# ── Export ─────────────────────────────────────────────────────────────────────

@api.post("/export")
def post_export(body: ExportRequest, user: dict = Depends(require_user)):
    """Export an expanded idea as a downloadable Markdown file."""
    owner_id = uuid.UUID(user["id"])
    run = get_run(run_id=body.run_id, owner_id=owner_id)
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
        run = get_run(run_id=body.run_id, owner_id=owner_id)
        assert run is not None
        idea = run["ideas"][body.pid - 1].copy()
        idea.pop("pid", None)
    else:
        logger.info(
            "No persisted expansion for run_id=%s pid=%s; expanding on demand.",
            body.run_id, body.pid,
        )
        expanded = graph_expand_idea(idea)
        extended_plan = expanded.get("extended_plan", [])
        idea = expanded.get("idea", idea)
        update_run_idea(run_id=body.run_id, pid=body.pid, idea=idea)
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
    user: dict = Depends(require_user),
    limit: int = Query(default=20, ge=1, le=100, description="Max runs to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """Return the user's past runs, most recent first."""
    runs = load_history(user_id=uuid.UUID(user["id"]), limit=limit, offset=offset)
    return {"runs": runs, "limit": limit, "offset": offset}


@api.get("/runs/{run_id}")
def get_run_detail(run_id: str, user: dict = Depends(require_user)):
    """Return full details of a single run including all ideas."""
    run = get_run(run_id=run_id, owner_id=uuid.UUID(user["id"]))
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found.",
        )
    return run


# ── Repository Intelligence / Analysis (Evidence-First) ──────────────────────

def _to_dict(obj) -> dict:
    """Normalize a pydantic model (or a dict/mock in tests) into a plain dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)


def _analysis_response(run_id: str, analysis: dict, graph: dict | None) -> dict:
    """The flat /analyze response body: the domain Analysis at top level (its
    `mermaid` architecture diagram included, may be null), plus the persisted
    `run_id` (used by GET /analyze/{run_id}) and the `graph` extra (the
    structural ProjectGraph, for a UI that renders the wiring natively)."""
    return {"run_id": run_id, **analysis, "graph": graph}


def _run_analyze_pipeline(target: str, repo_url: str | None, user_id: uuid.UUID) -> dict:
    """Run the evidence-first analysis pipeline and persist the result. Shared
    by the sync and async paths of POST /analyze — returns the same dict shape
    that is the sync path's 200 response body."""
    analysis, project_graph = analyze_repository_with_graph(target, repo_url=repo_url)
    graph_dict = _to_dict(project_graph)
    run_id = save_analysis_run(
        analysis, project_graph=graph_dict, repo_url=repo_url, user_id=user_id
    )
    return _analysis_response(run_id, _to_dict(analysis), graph_dict)


@api.post("/analyze")
def post_analyze(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_user),
    async_: bool = Query(False, alias="async"),
):
    """Produce an evidence-first Repository Intelligence Analysis: ingest the
    repo deterministically, run the analysis, and return the domain `Analysis`
    (Repository + Findings + Recommendations) plus the structural `graph`.

    Runs synchronously by default. Pass `?async=true` to schedule it as a
    background job and get back `{job_id, status}` immediately (202);
    poll GET /jobs/{job_id}.
    """
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="Set API_KEY in .env")
    if analyze_repository_with_graph is None or save_analysis_run is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Analyzer core modules (app.cartographer.pipeline/analysis_store) "
                "are not available yet."
            ),
        )

    target = body.repo_url or body.path
    owner_id = uuid.UUID(user["id"])

    if async_:
        if create_job is None or run_job is None:
            raise HTTPException(
                status_code=503,
                detail="Job runner module (app.services.jobs) is not available yet.",
            )
        job_id = create_job(kind="analyze", params={**body.model_dump(), "user_id": str(owner_id)})
        background_tasks.add_task(
            run_job, job_id, lambda: _run_analyze_pipeline(target, body.repo_url, owner_id)
        )
        return JSONResponse(status_code=202, content={"job_id": job_id, "status": "pending"})

    try:
        return _run_analyze_pipeline(target, body.repo_url, owner_id)
    except Exception as exc:
        logger.exception("Analyze pipeline failed for %r", target)
        raise HTTPException(status_code=500, detail=f"Analyze failed: {exc}") from exc


@api.get("/analyze/{run_id}")
def get_analyze_run_detail(run_id: str, user: dict = Depends(require_user)):
    """Return a previously persisted analysis run in the same flat shape as
    POST /analyze (Analysis fields + `graph` + `mermaid`), so the UI can
    reload a past run. 404 if it does not exist or isn't the caller's.
    """
    if get_analysis_run is None:
        raise HTTPException(
            status_code=503,
            detail="Analyzer core modules (app.cartographer.analysis_store) are not available yet.",
        )

    record = get_analysis_run(run_id, owner_id=uuid.UUID(user["id"]))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Analysis run {run_id} not found.")
    return _analysis_response(record["run_id"], record["analysis"], record.get("project_graph"))


@api.get("/analyses")
def list_analyses(
    user: dict = Depends(require_user),
    limit: int = Query(default=20, ge=1, le=100, description="Max analysis runs to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """List the caller's recent analysis runs as lightweight summary rows
    (run_id, repo_url, language, status, finding/recommendation counts,
    created_at) — most recent first. Mirrors GET /history's paging shape.
    """
    if list_analysis_runs is None:
        raise HTTPException(
            status_code=503,
            detail="Analyzer core modules (app.cartographer.analysis_store) are not available yet.",
        )
    analyses = list_analysis_runs(limit=limit, offset=offset, owner_id=uuid.UUID(user["id"]))
    return {"analyses": analyses, "limit": limit, "offset": offset}


# ── Async Jobs (F4) ───────────────────────────────────────────────────────────

def _assert_job_visible(record: dict, job_id: str, user_id: uuid.UUID) -> None:
    """404 a job that belongs to someone other than the caller.

    A job carrying no `user_id` param — or the anonymous one — is visible to
    anybody (pre-auth rows, AUTH_ENABLED=false). Compare as *strings*:
    `params` round-trips through JSONB so `user_id` comes back a str.
    """
    owner = (record.get("params") or {}).get("user_id")
    if owner is None or str(owner) == str(ANONYMOUS_USER_ID):
        return
    if str(owner) != str(user_id):
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found.",
        )


@api.get("/jobs/{job_id}")
def get_job_detail(job_id: str, user: dict = Depends(require_user)):
    """Return the status/result of a background job scheduled via
    `?async=true` on POST /analyze or POST /ideas: {job_id, kind, status,
    params, result, error, created_at, updated_at}. 404 if it does not exist,
    or if it belongs to another user.
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
    _assert_job_visible(record, job_id, uuid.UUID(user["id"]))
    return record


@api.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, user: dict = Depends(require_user)):
    """Subscribe to a background job's lifecycle over SSE (text/event-stream).

    A *view* of the in-process job (the job row is the source of truth):
    `status` events on change, a `heartbeat` after 30s of silence, then one
    terminal `done` (result JSON) or `error` event before closing. If the
    job is already terminal on subscribe (EventSource reconnect), that event
    is replayed immediately and the stream closes. 404 if the job does not
    exist, or if it belongs to another user. The upstream proxy must not
    buffer this path (see app.services.sse.SSE_HEADERS).
    """
    if get_job is None:
        raise HTTPException(
            status_code=503,
            detail="Job runner module (app.services.jobs) is not available yet.",
        )

    # to_thread: this route is async, so calling the sync DB read directly
    # would block the event loop for a full round trip on every subscribe.
    record = await asyncio.to_thread(get_job, job_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found.",
        )
    _assert_job_visible(record, job_id, uuid.UUID(user["id"]))
    # Hand the record we just read to the stream as its first pass, so the
    # gate read above is the only full-row hydration a subscribe costs. For an
    # already-terminal job (the EventSource reconnect path) that makes the
    # whole stream zero additional reads.
    return StreamingResponse(
        job_event_stream(
            job_id,
            get_job_fn=get_job,
            get_status_fn=get_job_status,
            initial_record=record,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


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
