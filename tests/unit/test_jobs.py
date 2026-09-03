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
from app.services.jobs import JobStatus, create_job, get_job, get_job_status, run_job


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


class FakeResult:
    """Stand-in for a SQLAlchemy Result, for the one narrow read jobs.py does."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    """Stand-in for a SQLAlchemy Session, backed by an in-memory dict keyed
    by uuid. Supports exactly the operations app.services.jobs uses:
    session.add(row), session.flush(), session.get(Model, uuid),
    session.execute(stmt, params)."""

    def __init__(self, store: dict):
        self._store = store

    def add(self, row: FakeJobRow) -> None:
        self._store[row.id] = row

    def flush(self) -> None:
        pass

    def get(self, _model, id_: uuid.UUID):
        return self._store.get(id_)

    def execute(self, _stmt, params=None):
        """Minimal stand-in for get_job_status's raw status select.

        Deliberately does not parse SQL — it answers the only statement
        jobs.py executes. If this ever needs to inspect _stmt, the production
        code has grown a query this fake should not be guessing at.
        """
        # jobs.py binds the id as a string and casts it in SQL; the store is
        # keyed by uuid.UUID, so parse it back the way Postgres would.
        raw_id = (params or {}).get("id")
        try:
            key = uuid.UUID(str(raw_id))
        except (ValueError, TypeError, AttributeError):
            return FakeResult(None)
        row = self._store.get(key)
        return FakeResult(row.status if row is not None else None)


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
    job_id = create_job(kind="analyze", params={"repo_url": "https://example.com/repo"})
    assert isinstance(job_id, str)
    # round-trips through uuid.UUID without raising
    uuid.UUID(job_id)


def test_create_job_persists_pending_status(fake_db):
    job_id = create_job(kind="analyze", params={"repo_url": "https://example.com/repo"})
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == JobStatus.PENDING.value
    assert job["kind"] == "analyze"
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


def test_get_job_status_returns_status(fake_db):
    job_id = create_job(kind="ideas", params={})
    assert get_job_status(job_id) == JobStatus.PENDING.value

    run_job(job_id, lambda: {"ok": True})
    assert get_job_status(job_id) == JobStatus.DONE.value


def test_get_job_status_unknown_id_returns_none(fake_db):
    assert get_job_status(str(uuid.uuid4())) is None


def test_get_job_status_malformed_id_returns_none(fake_db):
    # Same contract as get_job: user-supplied path params must not raise.
    assert get_job_status("not-a-uuid") is None
    assert get_job_status("") is None
    assert get_job_status("12345") is None


def test_run_job_success_marks_done_and_stores_result(fake_db):
    job_id = create_job(kind="analyze", params={})

    def fn():
        return {"ok": True, "value": 42}

    run_job(job_id, fn)

    job = get_job(job_id)
    assert job["status"] == JobStatus.DONE.value
    assert job["result"] == {"ok": True, "value": 42}
    assert job["error"] is None


def test_run_job_failure_marks_error_and_does_not_raise(fake_db):
    job_id = create_job(kind="analyze", params={})

    def fn():
        raise ValueError("boom")

    run_job(job_id, fn)  # must not raise

    job = get_job(job_id)
    assert job["status"] == JobStatus.ERROR.value
    assert job["error"] == "boom"
    assert job["result"] is None


def test_run_job_updates_updated_at(fake_db):
    job_id = create_job(kind="analyze", params={})
    before = get_job(job_id)["updated_at"]

    run_job(job_id, lambda: {"done": True})

    after = get_job(job_id)["updated_at"]
    assert after >= before


def test_run_job_unknown_job_id_does_not_raise(fake_db):
    # Should log and return quietly rather than propagate - run_job's
    # contract says it must NEVER raise (it's the target of
    # BackgroundTasks.add_task, whose caller can't observe exceptions).
    run_job(str(uuid.uuid4()), lambda: {"ok": True})
