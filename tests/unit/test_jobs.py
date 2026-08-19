"""Unit tests for app.services.jobs.

No real Postgres connection is made: app.services.jobs.get_session is
monkeypatched to a fake context manager backed by an in-memory dict, mirroring
how the rest of this suite avoids real DB/LLM I/O (see tests/conftest.py).
"""

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from app.services import jobs as jobs_module
from app.services.jobs import JobStatus, create_job, get_job, run_job


class FakeJobRow:
    """Stand-in for app.services.models.Job - just needs the attributes
    app.services.jobs reads/writes."""

    def __init__(self, kind: str, status: str, params: dict):
        self.id = uuid.uuid4()
        self.kind = kind
        self.status = status
        self.params = params
        self.result = None
        self.error = None
        now = datetime.now(UTC)
        self.created_at = now
        self.updated_at = now


class FakeSession:
    """Stand-in for a SQLAlchemy Session, backed by an in-memory dict keyed
    by uuid. Supports exactly the operations app.services.jobs uses:
    session.add(row), session.flush(), session.get(Model, uuid)."""

    def __init__(self, store: dict):
        self._store = store

    def add(self, row: FakeJobRow) -> None:
        self._store[row.id] = row

    def flush(self) -> None:
        pass

    def get(self, _model, id_: uuid.UUID):
        return self._store.get(id_)


@pytest.fixture()
def fake_db(monkeypatch):
    """Monkeypatch app.services.jobs.get_session to yield a FakeSession
    backed by a persistent in-memory store, and app.services.jobs.Job to
    build FakeJobRow instances instead of the real SQLAlchemy model."""
    store: dict[uuid.UUID, FakeJobRow] = {}

    @contextmanager
    def fake_get_session():
        yield FakeSession(store)

    def fake_job_ctor(*, kind, status, params):
        return FakeJobRow(kind=kind, status=status, params=params)

    monkeypatch.setattr(jobs_module, "get_session", fake_get_session)
    monkeypatch.setattr(jobs_module, "Job", fake_job_ctor)
    return store


def test_create_job_returns_string_id(fake_db):
    job_id = create_job(kind="cartograph", params={"repo_url": "https://example.com/repo"})
    assert isinstance(job_id, str)
    # round-trips through uuid.UUID without raising
    uuid.UUID(job_id)


def test_create_job_persists_pending_status(fake_db):
    job_id = create_job(kind="advise", params={"repo_url": "https://example.com/repo"})
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.PENDING.value
    assert job["kind"] == "advise"
    assert job["params"] == {"repo_url": "https://example.com/repo"}
    assert job["result"] is None
    assert job["error"] is None
    assert isinstance(job["created_at"], str)
    assert isinstance(job["updated_at"], str)


def test_get_job_unknown_id_returns_none(fake_db):
    assert get_job(str(uuid.uuid4())) is None


def test_get_job_malformed_id_returns_none(fake_db):
    assert get_job("not-a-uuid") is None
    assert get_job("") is None
    assert get_job("12345") is None


def test_run_job_success_marks_done_and_stores_result(fake_db):
    job_id = create_job(kind="cartograph", params={})

    def fn():
        return {"ok": True, "value": 42}

    run_job(job_id, fn)

    job = get_job(job_id)
    assert job["status"] == JobStatus.DONE.value
    assert job["result"] == {"ok": True, "value": 42}
    assert job["error"] is None


def test_run_job_failure_marks_error_and_does_not_raise(fake_db):
    job_id = create_job(kind="advise", params={})

    def fn():
        raise ValueError("boom")

    run_job(job_id, fn)  # must not raise

    job = get_job(job_id)
    assert job["status"] == JobStatus.ERROR.value
    assert job["error"] == "boom"
    assert job["result"] is None


def test_run_job_updates_updated_at(fake_db):
    job_id = create_job(kind="cartograph", params={})
    before = get_job(job_id)["updated_at"]

    run_job(job_id, lambda: {"done": True})

    after = get_job(job_id)["updated_at"]
    assert after >= before


def test_run_job_unknown_job_id_does_not_raise(fake_db):
    # Should log and return quietly rather than propagate - run_job's
    # contract says it must NEVER raise (it's the target of
    # BackgroundTasks.add_task, whose caller can't observe exceptions).
    run_job(str(uuid.uuid4()), lambda: {"ok": True})
