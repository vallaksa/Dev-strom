"""Unit tests for the SSE wire helpers in app/services/sse.py.

No real jobs/DB: the generator tests drive `job_event_stream` with a fake
`get_job` monkeypatched onto the sse module namespace. Async generators are
driven with asyncio.run so no async pytest plugin is required.
"""

import asyncio
import json

import pytest

from app.services import sse as sse_module
from app.services.sse import format_sse


# ── format_sse ────────────────────────────────────────────────────────────────

def test_format_sse_named_event_and_json_data():
    raw = format_sse("status", {"status": "running"})
    assert raw == 'event: status\ndata: {"status": "running"}\n\n'


def test_format_sse_data_is_valid_json():
    raw = format_sse("done", {"ideas": [1, 2], "run_id": "r1"})
    payload = raw.split("data: ", 1)[1].strip()
    assert json.loads(payload) == {"ideas": [1, 2], "run_id": "r1"}


def test_format_sse_heartbeat_shape():
    raw = format_sse("heartbeat", {"ts": "2026-09-01T16:22:00+00:00"})
    assert raw.startswith("event: heartbeat\ndata: ")


# ── job_event_stream ──────────────────────────────────────────────────────────

def _collect(async_gen) -> list:
    """Drain an async generator into a list of SSE chunk strings."""
    async def run():
        return [chunk async for chunk in async_gen]

    return asyncio.run(run())


def _events(chunks):
    """Parse SSE chunks into (event, data_dict) tuples."""
    out = []
    for chunk in chunks:
        event = None
        data = None
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        out.append((event, data))
    return out


class _ScriptedJobs:
    """Fake get_job returning a scripted sequence of job records per poll."""

    def __init__(self, states):
        self.states = list(states)  # each: full job-record dict
        self.polls = 0

    def __call__(self, job_id):
        self.polls += 1
        if self.polls <= len(self.states):
            return self.states[self.polls - 1]
        # stay on last state forever (should never be reached when terminal)
        return self.states[-1]


def _job(status, result=None, error=None, user_id=None):
    return {
        "job_id": "job-1", "kind": "ideas", "status": status,
        "params": {"user_id": user_id} if user_id else {},
        "result": result, "error": error,
    }


def test_stream_emits_status_changes_then_done(monkeypatch):
    script = _ScriptedJobs([
        _job("pending"),
        _job("running"),
        _job("done", result={"ideas": [{"name": "A"}], "run_id": "r1"}),
    ])
    monkeypatch.setattr(sse_module, "get_job", script)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    events = _events(chunks)

    assert events == [
        ("status", {"status": "pending"}),
        ("status", {"status": "running"}),
        ("done", {"ideas": [{"name": "A"}], "run_id": "r1"}),
    ]


def test_stream_already_done_emits_single_done_and_closes(monkeypatch):
    script = _ScriptedJobs([_job("done", result={"ok": True})])
    monkeypatch.setattr(sse_module, "get_job", script)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    assert _events(chunks) == [("done", {"ok": True})]


def test_stream_error_status_emits_error_then_stops(monkeypatch):
    script = _ScriptedJobs([_job("error", error="boom")])
    monkeypatch.setattr(sse_module, "get_job", script)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    assert _events(chunks) == [("error", {"error": "boom"})]


def test_stream_heartbeat_on_silence(monkeypatch):
    # Same status ("running") across enough clock ticks to cross the
    # heartbeat interval, then done. Fake clock: +1 tick per call.
    now = {"t": 0.0}

    def fake_clock():
        now["t"] += 1.0
        return now["t"]

    script = _ScriptedJobs([
        _job("running"),
        _job("running"),
        _job("running"),
        _job("done", result={"x": 1}),
    ])
    monkeypatch.setattr(sse_module, "get_job", script)

    chunks = _collect(
        sse_module.job_event_stream(
            "job-1", poll_interval=0, heartbeat_interval=1.0, clock=fake_clock
        )
    )
    events = _events(chunks)

    assert events == [
        ("status", {"status": "running"}),
        ("heartbeat", {"ts": events[1][1]["ts"]}),
        ("heartbeat", {"ts": events[2][1]["ts"]}),
        ("done", {"x": 1}),
    ]
    assert "ts" in events[1][1]


def test_stream_missing_job_midstream_emits_error(monkeypatch):
    calls = {"n": 0}

    def fake_get_job(job_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return _job("running")
        return None

    monkeypatch.setattr(sse_module, "get_job", fake_get_job)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    events = _events(chunks)
    assert events[0] == ("status", {"status": "running"})
    assert events[1][0] == "error"


def test_stream_uses_asyncio_to_thread(monkeypatch):
    """get_job must be called via asyncio.to_thread (off the event loop)."""
    seen = []

    def fake_get_job(job_id):
        seen.append(job_id)
        return _job("done", result={"ok": 1})

    monkeypatch.setattr(sse_module, "get_job", fake_get_job)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    assert chunks and seen == ["job-1"]


def test_sse_headers_constant():
    headers = sse_module.SSE_HEADERS
    assert headers["Cache-Control"] == "no-cache, no-transform"
    assert headers["Connection"] == "keep-alive"
    assert headers["X-Accel-Buffering"] == "no"
