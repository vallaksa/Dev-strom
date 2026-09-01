"""SSE wire helpers: canonical event framing and a job-backed event stream.

SSE here is a *view* of an in-process job (app.services.jobs), not the
worker: the job row is the source of truth, and a dropped stream (e.g.
Cloudflare killing a ~100s connection) never kills the work — the client
reconnects (EventSource) and the already-terminal catch-up below replays
the final event. Caddy/Tunnel should not buffer this path.

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

from app.services.jobs import get_job

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

TERMINAL_STATUSES = {"done", "error"}


def format_sse(event: str, data: dict) -> str:
    """One framed SSE event: `event:` line, JSON `data:` line, blank line."""
    return f"event: {event}\ndata: {json.dumps(data, separators=(', ', ': '))}\n\n"


async def job_event_stream(
    job_id: str,
    *,
    poll_interval: float = 1.0,
    heartbeat_interval: float = 15.0,
    clock=time.monotonic,
    get_job_fn=None,
) -> AsyncIterator[str]:
    """Yield SSE frames for the lifecycle of job `job_id`.

    Polls `get_job` every `poll_interval` seconds (via `asyncio.to_thread`,
    so the sync DB call never blocks the event loop). Emits `status` only on
    change, a `heartbeat` after `heartbeat_interval` seconds of silence, and
    one terminal `done`/`error` event before closing. If the job is already
    terminal on the first poll (EventSource reconnect), emits that event
    immediately and closes. If the row vanishes mid-stream, emits one
    `error` event and closes — never raises out of the generator.
    """
    last_status = None
    last_emit_time = clock()
    get_job_fn = get_job_fn or get_job

    while True:
        try:
            record = await asyncio.to_thread(get_job_fn, job_id)
        except Exception as exc:  # DB hiccup: one error event, then close.
            yield format_sse("error", {"error": f"Failed to read job: {exc}"})
            return

        if record is None:
            # Row vanished mid-stream (or was never readable): map to error.
            yield format_sse("error", {"error": f"Job {job_id} not found."})
            return

        status = record.get("status")
        if status in TERMINAL_STATUSES:
            # Terminal: the done/error frame *is* the transition — never emit
            # a redundant `status` frame for it. First poll (reconnect) is the
            # catch-up path: just the terminal event, then close.
            if status == "done":
                yield format_sse("done", record.get("result") or {})
            else:
                yield format_sse("error", {"error": record.get("error") or "Job failed."})
            return

        if status != last_status:
            yield format_sse("status", {"status": status})
            last_status = status
            last_emit_time = clock()
        elif (clock() - last_emit_time) >= heartbeat_interval:
            yield format_sse(
                "heartbeat", {"ts": datetime.now(UTC).isoformat()}
            )
            last_emit_time = clock()

        if status == "done":
            yield format_sse("done", record.get("result") or {})
            return
        if status == "error":
            yield format_sse("error", {"error": record.get("error") or "Job failed."})
            return

        await asyncio.sleep(poll_interval)
