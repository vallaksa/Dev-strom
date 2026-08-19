"""Dev-Strom FastAPI server.

Exposes endpoints for idea generation, expansion, export, and history.
All runs are persisted to PostgreSQL. Until auth is implemented, all
operations use the ANONYMOUS_USER_ID.
"""

import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.models.dto import CartographRequest, ExpandRequest, ExportRequest, IdeasRequest

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
# app.cartographer.{analyze,pipeline,store} are owned by a parallel branch
# (feat/f1-core) and may not exist yet in this worktree. Import them lazily
# and guard with try/except so app.api stays importable (and every existing
# route/test above keeps working) whether or not feat/f1-core has landed. The
# /cartograph routes below check for None and return a clear 503 instead.
try:
    from app.cartographer.analyze import analyze_architecture
    from app.cartographer.pipeline import cartograph
    from app.cartographer.store import get as get_cartograph_run
    from app.cartographer.store import save as save_cartograph_run
except ImportError:
    analyze_architecture = None
    cartograph = None
    get_cartograph_run = None
    save_cartograph_run = None

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


@api.post("/cartograph")
def post_cartograph(body: CartographRequest):
    """Map a repository's architecture: build a ProjectGraph, analyze it into
    an ArchitectureReport, persist both, and return them. Synchronous MVP —
    the clone/parse/analyze pipeline runs inline on the request.
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
    try:
        project_graph = cartograph(target, repo_url=body.repo_url)
        architecture_report = analyze_architecture(project_graph)
    except Exception as exc:
        logger.exception("Cartograph pipeline failed for %r", target)
        raise HTTPException(
            status_code=500,
            detail=f"Cartograph failed: {exc}",
        ) from exc

    run_id = save_cartograph_run(project_graph, architecture_report)

    return {
        "run_id": run_id,
        "project_graph": _to_dict(project_graph),
        "architecture_report": _to_dict(architecture_report),
    }


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
