"""Minimal in-process background job runner.

Not a task queue (no Celery/Redis/etc): per docs/PLAN.md's bias towards lean,
just-in-time infra, this is deliberately just three functions plus a
Postgres-backed record, designed to be handed to FastAPI's
`BackgroundTasks.add_task(...)`:

    job_id = create_job(kind="analyze", params={"repo_url": repo_url})
    background_tasks.add_task(run_job, job_id, lambda: run_analyze_pipeline(repo_url))
    return {"job_id": job_id}

and later polled via:

    GET /jobs/{job_id} -> get_job(job_id)

Persistence follows the same get_session()/ORM pattern as
app.cartographer.analysis_store.PostgresJsonbStore and app.services.run_service -
see those modules for the canonical idiom this one copies.
"""

import logging
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable

from app.services.db import get_session
from app.services.models import Job

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


def create_job(kind: str, params: dict) -> str:
    """Insert a new job row with status=PENDING, kind=kind, params=params.

    Returns the new job's id as a string (str(uuid)).
    """
    row = Job(kind=kind, status=JobStatus.PENDING.value, params=params)
    with get_session() as session:
        session.add(row)
        session.flush()  # populate row.id before commit
        job_id = str(row.id)
    logger.info("Created job %s (kind=%s)", job_id, kind)
    return job_id


def get_job(job_id: str) -> dict | None:
    """Fetch a job by id. Returns None if it doesn't exist, and also returns
    None (rather than raising) if job_id is not a well-formed UUID - this is
    expected to be called from a GET /jobs/{job_id} route with user-supplied
    input.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except (ValueError, TypeError, AttributeError):
        return None
    with get_session() as session:
        row = session.get(Job, job_uuid)
        if row is None:
            return None
        return _row_to_dict(row)


def run_job(job_id: str, fn: Callable[[], dict[str, Any]]) -> None:
    """Mark the job RUNNING, call fn() with no arguments, store its return
    value as `result`, mark DONE. If fn() raises, catch the exception, store
    str(exc) in `error`, mark ERROR.

    This function must NEVER raise - it's designed to be the target of
    `BackgroundTasks.add_task(run_job, job_id, fn)`, and FastAPI has no way
    to surface an exception from a background task back to the client (the
    response was already sent).
    """
    try:
        _set_status(job_id, JobStatus.RUNNING)
    except Exception:
        logger.exception("jobs: failed to mark job %s RUNNING", job_id)
        # Fall through and still attempt to run fn() - a failure to persist
        # the RUNNING transition shouldn't stop the job from executing.

    try:
        result = fn()
    except Exception as exc:
        logger.exception("jobs: job %s raised while running", job_id)
        try:
            _finish(job_id, JobStatus.ERROR, error=str(exc))
        except Exception:
            logger.exception("jobs: failed to persist ERROR status for job %s", job_id)
        return

    try:
        _finish(job_id, JobStatus.DONE, result=result)
    except Exception:
        logger.exception("jobs: failed to persist DONE status for job %s", job_id)


# ── internal helpers ──────────────────────────────────────────────────────────


def _row_to_dict(row: Job) -> dict:
    return {
        "job_id": str(row.id),
        "kind": row.kind,
        "status": row.status,
        "params": row.params,
        "result": row.result,
        "error": row.error,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _set_status(job_id: str, status: JobStatus) -> None:
    with get_session() as session:
        row = session.get(Job, uuid.UUID(job_id))
        if row is None:
            raise ValueError(f"job {job_id} not found")
        row.status = status.value
        row.updated_at = datetime.now(UTC)


def _finish(
    job_id: str,
    status: JobStatus,
    *,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    with get_session() as session:
        row = session.get(Job, uuid.UUID(job_id))
        if row is None:
            raise ValueError(f"job {job_id} not found")
        row.status = status.value
        row.result = result
        row.error = error
        row.updated_at = datetime.now(UTC)
