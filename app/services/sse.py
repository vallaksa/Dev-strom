"""SSE wire helpers: canonical event framing and a job-backed event stream.

SSE here is a *view* of an in-process job (app.services.jobs), not the
worker: the job row is the source of truth, and a dropped stream (e.g.
Cloudflare killing a ~100s connection) never kills the work — the client
reconnects (EventSource) and the already-terminal catch-up below replays
the final event. Caddy/Tunnel should not buffer this path.

Polling, not push: the job may run in a *different* uvicorn worker process
than the one serving this stream, so an in-process asyncio.Event registry
would silently fail to fire. A poll against the shared job row is correct
across processes, which is worth far more than the handful of indexed
primary-key reads it costs. Those reads are kept cheap by (a) polling a
status-only query and hydrating the full row just once, on the terminal
transition, and (b) backing the poll interval off from `poll_interval` to
`max_poll_interval` while nothing changes.

Wire format — named events, JSON `data:` lines, blank-line terminator:

    event: status
    data: {"status": "running"}

    event: heartbeat
    data: {"ts": "2026-09-01T16:22:00+00:00"}

    event: done
    data: { ...job.result... }
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.services.jobs import get_job, get_job_status

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

TERMINAL_STATUSES = {"done", "error"}

# Multiplier applied to the poll interval after each unchanged poll. Note
# `poll_interval=0` (used by the tests) stays 0 under multiplication, so
# backoff self-disables there.
BACKOFF_FACTOR = 1.5

# Job errors are `str(exc)` from the pipeline, which for an LLM provider
# failure can be a multi-kilobyte dump. Cap what goes on the wire.
MAX_ERROR_CHARS = 500


def format_sse(event: str, data: dict) -> str:
    """One framed SSE event: `event:` line, JSON `data:` line, blank line."""
    return f"event: {event}\ndata: {json.dumps(data, separators=(', ', ': '))}\n\n"


def _error_frame(message: str) -> str:
    """A terminal `error` frame, with the message capped at MAX_ERROR_CHARS."""
    if len(message) > MAX_ERROR_CHARS:
        message = message[:MAX_ERROR_CHARS] + "…"
    return format_sse("error", {"error": message})


def _next_poll_interval(current: float, *, factor: float, ceiling: float) -> float:
    """Ramp the poll delay after a poll that saw no change.

    A job that has been running for 30s is unlikely to finish in the next
    250ms, so back off — but keep the first few polls tight so short jobs stay
    snappy. `current == 0` (every generator unit test) stays 0, which is what
    keeps those tests spinning at full speed.
    """
    return min(current * factor, ceiling)


async def job_event_stream(
    job_id: str,
    *,
    poll_interval: float = 0.25,
    max_poll_interval: float = 2.0,
    heartbeat_interval: float = 30.0,
    max_duration: float = 300.0,
    clock=time.monotonic,
    get_job_fn=None,
    get_status_fn=None,
    initial_record: dict | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames for the lifecycle of job `job_id`.

    Polls the job's status (via `asyncio.to_thread`, so the sync DB call
    never blocks the event loop), starting at `poll_interval` seconds and
    backing off by BACKOFF_FACTOR up to `max_poll_interval` while the status
    is unchanged — a status change resets it, so transitions stay snappy
    without paying for a tight loop across a multi-minute job. Emits `status`
    only on change, a `heartbeat` after `heartbeat_interval` seconds of
    silence, and one terminal `done`/`error` event before closing.

    `initial_record` is the full job record the caller has already fetched
    (the route reads one for its 404/ownership gate); supplying it saves a
    redundant read on the first pass.

    If the job is already terminal on the first pass (EventSource reconnect),
    emits that event immediately and closes. If the row vanishes mid-stream,
    emits one `error` event and closes. If the job is still un-terminal after
    `max_duration` seconds, emits one `error` event and closes rather than
    streaming forever — jobs run in-process via BackgroundTasks and do not
    survive a restart, so a stranded `running` row would otherwise hold the
    connection (and the client's promise) open indefinitely. Never raises out
    of the generator.
    """
    get_job_fn = get_job_fn or get_job
    get_status_fn = get_status_fn or get_job_status

    start = clock()
    last_emit_time = start
    last_status = None
    interval = poll_interval
    # Full record for the first pass, when the caller already had one.
    record = initial_record

    while True:
        if record is not None:
            status = record.get("status")
        else:
            try:
                status = await asyncio.to_thread(get_status_fn, job_id)
            except Exception as exc:  # DB hiccup: one error event, then close.
                yield _error_frame(f"Failed to read job: {exc}")
                return

        if status is None:
            # Row vanished mid-stream (or was never readable): map to error.
            # `status` is NOT NULL in the schema, so None is unambiguous.
            yield _error_frame(f"Job {job_id} not found.")
            return

        # One clock read per iteration: the heartbeat unit test injects a fake
        # clock that advances per *call*, so the read count per loop is part of
        # the observable behaviour. Keep it at exactly one.
        now = clock()

        if status in TERMINAL_STATUSES:
            # Terminal: the done/error frame *is* the transition — never emit
            # a redundant `status` frame for it. First pass (reconnect) is the
            # catch-up path: just the terminal event, then close. Hydrate the
            # full row here, the one place `result`/`error` are actually read.
            if record is None:
                try:
                    record = await asyncio.to_thread(get_job_fn, job_id)
                except Exception as exc:
                    yield _error_frame(f"Failed to read job: {exc}")
                    return
                if record is None:
                    yield _error_frame(f"Job {job_id} not found.")
                    return
            if status == "done":
                yield format_sse("done", record.get("result") or {})
            else:
                yield _error_frame(record.get("error") or "Job failed.")
            return

        if now - start >= max_duration:
            yield _error_frame(
                f"Job {job_id} is still running after {max_duration:.0f}s; "
                f"stopped streaming. Reconnect, or poll GET /jobs/{job_id}."
            )
            return

        if status != last_status:
            yield format_sse("status", {"status": status})
            last_status = status
            last_emit_time = now
            interval = poll_interval  # progress: drop back to a tight poll
        elif (now - last_emit_time) >= heartbeat_interval:
            yield format_sse("heartbeat", {"ts": datetime.now(UTC).isoformat()})
            last_emit_time = now

        record = None  # consumed; subsequent passes poll for status only
        await asyncio.sleep(interval)
        interval = _next_poll_interval(
            interval, factor=BACKOFF_FACTOR, ceiling=max_poll_interval
        )
