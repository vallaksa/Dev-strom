"""Run persistence service.

Handles saving idea-generation runs and expanded ideas to PostgreSQL,
and retrieving run history for the history page.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.db import get_session
from app.services.models import ANONYMOUS_USER_ID, ExpandedIdea, Run
from app.services.slugs import get_by_public_id, insert_with_unique_slug, public_id, slugify


def save_run(
    *,
    tech_stack: str,
    domain: str | None,
    level: str | None,
    count: int,
    enable_multi_query: bool,
    ideas: list[dict],
    web_context: str | None,
    user_id: uuid.UUID = ANONYMOUS_USER_ID,
) -> str:
    """Insert a new run into the database and return the public run_id (slug)."""
    return insert_with_unique_slug(
        Run,
        slugify(tech_stack),
        lambda _session, slug: Run(
            slug=slug,
            user_id=user_id,
            tech_stack=tech_stack,
            domain=domain,
            level=level,
            count=count,
            enable_multi_query=enable_multi_query,
            ideas=ideas,
            web_context=web_context,
        ),
    )


def _run_or_raise(session: Session, run_id: str) -> Run:
    run = get_by_public_id(session, Run, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found.")
    return run


def update_run_idea(*, run_id: str, pid: int, idea: dict) -> None:
    """Merge fields into one idea position inside a persisted run."""
    with get_session() as session:
        run = _run_or_raise(session, run_id)
        ideas = list(run.ideas)
        idx = pid - 1
        if idx < 0 or idx >= len(ideas):
            raise ValueError(f"Invalid pid {pid} for run {run_id}.")
        merged = {**ideas[idx], **idea}
        merged["pid"] = pid
        ideas[idx] = merged
        run.ideas = ideas


def save_expanded_idea(
    *,
    run_id: str,
    pid: int,
    extended_plan: list[str],
) -> str:
    """Persist an expanded idea linked to a run and idea position."""
    with get_session() as session:
        run = _run_or_raise(session, run_id)
        expanded = ExpandedIdea(
            run_id=run.id,
            pid=pid,
            extended_plan=extended_plan,
        )
        session.add(expanded)
        session.flush()
        expanded_id = str(expanded.id)
    return expanded_id


def get_latest_expansion(*, run_id: str, pid: int) -> dict | None:
    """Fetch the most recently persisted expansion for (run_id, pid)."""
    with get_session() as session:
        run = get_by_public_id(session, Run, run_id)
        if run is None:
            return None
        stmt = (
            select(ExpandedIdea)
            .where(ExpandedIdea.run_id == run.id, ExpandedIdea.pid == pid)
            .order_by(ExpandedIdea.created_at.desc())
            .limit(1)
        )
        expanded = session.execute(stmt).scalars().first()
        if expanded is None:
            return None
        return {
            "id": str(expanded.id),
            "run_id": public_id(run),
            "pid": expanded.pid,
            "extended_plan": expanded.extended_plan,
            "created_at": expanded.created_at.isoformat(),
        }


def load_history(
    *,
    user_id: uuid.UUID = ANONYMOUS_USER_ID,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """Fetch the user's past runs, most recent first.

    Returns a list of dicts with run metadata (no full ideas blob —
    call get_run() for the full payload). `run_id` is the public slug.
    """
    with get_session() as session:
        stmt = (
            select(Run)
            .where(Run.user_id == user_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        runs = session.execute(stmt).scalars().all()
        return [
            {
                "run_id": public_id(r),
                "tech_stack": r.tech_stack,
                "domain": r.domain,
                "level": r.level,
                "count": r.count,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]


def get_run(*, run_id: str, owner_id: uuid.UUID | None = None) -> dict | None:
    """Fetch a single run by slug or UUID, including the full ideas payload.

    Returns None if the run does not exist — or, when `owner_id` is given,
    if the run belongs to a different user (callers surface both as 404 so
    ownership isn't leaked). `run_id` in the result is the slug.
    """
    with get_session() as session:
        run = get_by_public_id(session, Run, run_id)
        if run is None:
            return None
        if owner_id is not None and run.user_id != owner_id:
            return None
        return {
            "run_id": public_id(run),
            "user_id": str(run.user_id),
            "tech_stack": run.tech_stack,
            "domain": run.domain,
            "level": run.level,
            "count": run.count,
            "enable_multi_query": run.enable_multi_query,
            "ideas": run.ideas,
            "web_context": run.web_context,
            "created_at": run.created_at.isoformat(),
        }
