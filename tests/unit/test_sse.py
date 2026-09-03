"""Unit tests for the SSE wire helpers in app/services/sse.py.

No real jobs/DB: the generator tests drive `job_event_stream` with a fake
`get_job` monkeypatched onto the sse module namespace. Async generators are
driven with asyncio.run so no async pytest plugin is required.
"""

import asyncio
import json

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


def _ticking_clock(step: float):
    """A fake clock that advances `step` on every call.

    job_event_stream reads the clock exactly once per loop iteration (plus
    once before the loop), which is what makes a per-call fake predictable —
    see the comment above its loop before changing that.
    """
    now = {"t": 0.0}

    def clock():
        now["t"] += step
        return now["t"]

    return clock


class _ScriptedJobs:
    """Fake job store returning a scripted sequence of job records.

    The stream reads status and full records through two different seams: it
    polls `get_job_status` once per tick (one narrow column) and calls
    `get_job` only on the terminal transition, to hydrate result/error. So
    `status` advances the script and `current` does not — `current` just
    re-reads whatever poll the script is on.
    """

    def __init__(self, states):
        self.states = list(states)  # each: full job-record dict
        self.polls = 0

    def status(self, job_id):
        self.polls += 1
        return self.current(job_id)["status"]

    def current(self, job_id):
        # Stay on the last state once the script is exhausted.
        return self.states[min(self.polls, len(self.states)) - 1]


def _install(monkeypatch, script):
    """Patch both module globals job_event_stream resolves at call time."""
    monkeypatch.setattr(sse_module, "get_job_status", script.status)
    monkeypatch.setattr(sse_module, "get_job", script.current)


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
    _install(monkeypatch, script)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    events = _events(chunks)

    assert events == [
        ("status", {"status": "pending"}),
        ("status", {"status": "running"}),
        ("done", {"ideas": [{"name": "A"}], "run_id": "r1"}),
    ]


def test_stream_already_done_emits_single_done_and_closes(monkeypatch):
    script = _ScriptedJobs([_job("done", result={"ok": True})])
    _install(monkeypatch, script)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    assert _events(chunks) == [("done", {"ok": True})]


def test_stream_error_status_emits_error_then_stops(monkeypatch):
    script = _ScriptedJobs([_job("error", error="boom")])
    _install(monkeypatch, script)

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
    _install(monkeypatch, script)

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

    def fake_status(job_id):
        calls["n"] += 1
        return "running" if calls["n"] == 1 else None

    def unreachable_get_job(job_id):
        raise AssertionError("the full row must not be hydrated for a non-terminal job")

    monkeypatch.setattr(sse_module, "get_job_status", fake_status)
    monkeypatch.setattr(sse_module, "get_job", unreachable_get_job)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    events = _events(chunks)
    assert events[0] == ("status", {"status": "running"})
    assert events[1][0] == "error"


def test_stream_hydrates_full_row_exactly_once(monkeypatch):
    """The poll reads status only; the full row is fetched once, on terminal.

    Both reads go through asyncio.to_thread so the sync DB calls stay off the
    event loop.
    """
    seen = []

    def fake_get_job(job_id):
        seen.append(job_id)
        return _job("done", result={"ok": 1})

    monkeypatch.setattr(sse_module, "get_job_status", lambda job_id: "done")
    monkeypatch.setattr(sse_module, "get_job", fake_get_job)

    chunks = _collect(sse_module.job_event_stream("job-1", poll_interval=0))
    assert chunks and seen == ["job-1"]


def test_stream_max_duration_emits_terminal_error(monkeypatch):
    """A job stranded in `running` must not stream forever.

    BackgroundTasks jobs are in-process and do not survive a restart, so a row
    left at `running` would otherwise hold the connection — and the client's
    promise — open indefinitely.
    """
    clock = _ticking_clock(step=10.0)
    monkeypatch.setattr(sse_module, "get_job_status", lambda job_id: "running")
    monkeypatch.setattr(sse_module, "get_job", lambda job_id: _job("running"))

    events = _events(
        _collect(
            sse_module.job_event_stream(
                "job-1",
                poll_interval=0,
                heartbeat_interval=1e9,  # isolate: no heartbeats in the way
                max_duration=25.0,
                clock=clock,
            )
        )
    )

    assert events[0] == ("status", {"status": "running"})
    assert events[-1][0] == "error"
    assert "still running after 25s" in events[-1][1]["error"]


def test_stream_status_read_raising_emits_error(monkeypatch):
    """A DB hiccup on the poll closes the stream cleanly, it does not raise."""
    def boom(job_id):
        raise RuntimeError("db down")

    monkeypatch.setattr(sse_module, "get_job_status", boom)

    events = _events(_collect(sse_module.job_event_stream("job-1", poll_interval=0)))
    assert len(events) == 1
    assert events[0][0] == "error"
    assert "db down" in events[0][1]["error"]


def test_stream_terminal_hydrate_raising_emits_error(monkeypatch):
    """Splitting poll from hydrate adds a second read; it needs the same guard."""
    def boom(job_id):
        raise RuntimeError("hydrate exploded")

    monkeypatch.setattr(sse_module, "get_job_status", lambda job_id: "done")
    monkeypatch.setattr(sse_module, "get_job", boom)

    events = _events(_collect(sse_module.job_event_stream("job-1", poll_interval=0)))
    assert len(events) == 1
    assert events[0][0] == "error"
    assert "hydrate exploded" in events[0][1]["error"]


def test_stream_row_vanishing_between_poll_and_hydrate_emits_error(monkeypatch):
    """Reading status and the full row separately opens a race: the row can be
    gone by the time the terminal transition hydrates it."""
    monkeypatch.setattr(sse_module, "get_job_status", lambda job_id: "done")
    monkeypatch.setattr(sse_module, "get_job", lambda job_id: None)

    events = _events(_collect(sse_module.job_event_stream("job-1", poll_interval=0)))
    assert len(events) == 1
    assert events[0][0] == "error"
    assert "not found" in events[0][1]["error"]


def test_stream_initial_record_skips_the_first_read(monkeypatch):
    """The route already read the row for its 404 gate — don't read it again."""
    def unreachable(job_id):
        raise AssertionError("initial_record must satisfy the first pass")

    monkeypatch.setattr(sse_module, "get_job_status", unreachable)
    monkeypatch.setattr(sse_module, "get_job", unreachable)

    events = _events(
        _collect(
            sse_module.job_event_stream(
                "job-1",
                poll_interval=0,
                initial_record=_job("done", result={"ok": 1}),
            )
        )
    )
    assert events == [("done", {"ok": 1})]


def test_stream_error_message_is_truncated(monkeypatch):
    """`str(exc)` from an LLM provider can be kilobytes; cap what goes on the wire."""
    script = _ScriptedJobs([_job("error", error="x" * 5000)])
    _install(monkeypatch, script)

    events = _events(_collect(sse_module.job_event_stream("job-1", poll_interval=0)))
    message = events[0][1]["error"]
    assert len(message) == sse_module.MAX_ERROR_CHARS + 1  # + the ellipsis
    assert message.endswith("…")


def test_next_poll_interval_ramps_and_caps():
    def step(current):
        return sse_module._next_poll_interval(current, factor=1.5, ceiling=2.0)

    assert step(0.25) == 0.375
    assert step(0.375) == 0.5625
    assert step(1.5) == 2.0  # capped
    assert step(2.0) == 2.0  # stays capped
    # Every generator test passes poll_interval=0 and relies on it staying 0.
    assert step(0.0) == 0.0


def test_stream_poll_interval_backs_off_and_resets_on_change(monkeypatch):
    """Back off while nothing changes; snap back to a tight poll on progress."""
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(sse_module.asyncio, "sleep", fake_sleep)
    script = _ScriptedJobs([
        _job("pending"),
        _job("pending"),
        _job("pending"),
        _job("running"),
        _job("done", result={}),
    ])
    _install(monkeypatch, script)

    _collect(
        sse_module.job_event_stream(
            "job-1",
            poll_interval=1.0,
            max_poll_interval=2.0,
            heartbeat_interval=1e9,
        )
    )

    # pending (change -> reset), pending, pending (capped), running (change ->
    # reset); the terminal `done` returns before sleeping again.
    assert sleeps == [1.0, 1.5, 2.0, 1.0]


def test_sse_headers_constant():
    headers = sse_module.SSE_HEADERS
    assert headers["Cache-Control"] == "no-cache, no-transform"
    assert headers["Connection"] == "keep-alive"
    assert headers["X-Accel-Buffering"] == "no"
