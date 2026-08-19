"""Minimal in-memory job runner used by app.api's async /cartograph and
/advise paths.

# TODO: remove once app.services.jobs lands
This is a stand-in for the real job-runner primitive being built in
parallel (F4-core) against the contract documented in the task that
introduced app.api's async support. It implements the exact same
signatures (create_job/get_job/run_job) with an in-memory store so the
async endpoints can be developed and tested in this worktree ahead of the
real implementation landing. The integrator should delete this file and
let the real app.services.jobs module take over - no other module should
need to change.
"""

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(kind: str, params: dict) -> str:
    """Insert a new job row (status=PENDING). Returns job_id as a string."""
    job_id = str(uuid.uuid4())
    now = _now()
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "status": JobStatus.PENDING.value,
            "params": params,
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
    return job_id


def get_job(job_id: str) -> dict | None:
    """Returns None if not found (including on a malformed id string - never
    raises). Otherwise the job record dict."""
    try:
        with _lock:
            record = _jobs.get(job_id)
            return dict(record) if record is not None else None
    except Exception:
        return None


def run_job(job_id: str, fn) -> None:
    """Marks the job RUNNING, calls fn() with no args, stores its return
    dict as `result` and marks DONE; on exception stores str(exc) as `error`
    and marks ERROR. Never raises. Designed for
    BackgroundTasks.add_task(run_job, job_id, fn)."""
    with _lock:
        record = _jobs.get(job_id)
        if record is None:
            return
        record["status"] = JobStatus.RUNNING.value
        record["updated_at"] = _now()

    try:
        result = fn()
        with _lock:
            record = _jobs.get(job_id)
            if record is not None:
                record["result"] = result
                record["status"] = JobStatus.DONE.value
                record["updated_at"] = _now()
    except Exception as exc:  # noqa: BLE001 - never raise out of a background task
        with _lock:
            record = _jobs.get(job_id)
            if record is not None:
                record["error"] = str(exc)
                record["status"] = JobStatus.ERROR.value
                record["updated_at"] = _now()
