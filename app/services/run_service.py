"""Run persistence service.

Handles saving idea-generation runs and expanded ideas to PostgreSQL,
and retrieving run history for the history page.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.db import get_session
from app.services.models import ANONYMOUS_USER_ID, ExpandedIdea, Run


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
    """Insert a new run into the database and return the run_id as a string.

    Args:
        tech_stack: The tech stack requested by the user.
        domain: Optional domain bias.
        level: Optional difficulty level.
        count: Number of ideas requested.
        enable_multi_query: Whether multi-query web search was enabled.
        ideas: The list of generated idea dicts.
        web_context: Raw Tavily web search text (may be None).
        user_id: Owner of this run. Defaults to anonymous until auth is added.

    Returns:
        The UUID of the newly created run, as a string.
    """
    run = Run(
        user_id=user_id,
        tech_stack=tech_stack,
        domain=domain,
        level=level,
        count=count,
        enable_multi_query=enable_multi_query,
        ideas=ideas,
        web_context=web_context,
    )
    with get_session() as session:
        session.add(run)
        session.flush()  # populate run.id before commit
        run_id = str(run.id)
    return run_id


def save_expanded_idea(
    *,
    run_id: str,
    pid: int,
    extended_plan: list[str],
) -> str:
    """Persist an expanded idea linked to a run and idea position.

    Args:
        run_id: The UUID of the parent run.
        pid: 1-based position of the idea within the run.
        extended_plan: The list of expanded implementation steps.

    Returns:
        The UUID of the newly created expanded_idea row, as a string.
    """
    expanded = ExpandedIdea(
        run_id=uuid.UUID(run_id),
        pid=pid,
        extended_plan=extended_plan,
    )
    with get_session() as session:
        session.add(expanded)
        session.flush()
        expanded_id = str(expanded.id)
    return expanded_id


def get_latest_expansion(*, run_id: str, pid: int) -> dict | None:
    """Fetch the most recently persisted expansion for (run_id, pid).

    Used by POST /export so it can reuse the extended_plan already written by
    a prior POST /expand call instead of calling the LLM again. Returns None
    if the idea at this (run_id, pid) has never been expanded.
    """
    with get_session() as session:
        stmt = (
            select(ExpandedIdea)
            .where(ExpandedIdea.run_id == uuid.UUID(run_id), ExpandedIdea.pid == pid)
            .order_by(ExpandedIdea.created_at.desc())
            .limit(1)
        )
        expanded = session.execute(stmt).scalars().first()
        if expanded is None:
            return None
        return {
            "id": str(expanded.id),
            "run_id": str(expanded.run_id),
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
    call get_run() for the full payload).
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
                "run_id": str(r.id),
                "tech_stack": r.tech_stack,
                "domain": r.domain,
                "level": r.level,
                "count": r.count,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]


def get_run(*, run_id: str) -> dict | None:
    """Fetch a single run by ID, including the full ideas payload.

    Returns None if the run does not exist.
    """
    with get_session() as session:
        run = session.get(Run, uuid.UUID(run_id))
        if run is None:
            return None
        return {
            "run_id": str(run.id),
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
