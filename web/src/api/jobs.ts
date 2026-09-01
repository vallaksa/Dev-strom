/**
 * SSE job stream client — mirrors app/services/sse.py.
 *
 * `subscribeJob` opens an EventSource on GET /api/jobs/{job_id}/events and
 * resolves with the job's terminal result. The backend frames:
 *
 *   event: status     data: {"status": "running"}
 *   event: heartbeat  data: (ignored)
 *   event: done       data: { ...job.result... }
 *   event: error      data: {"message": ...}  (or text detail)
 *
 * One terminal `done`/`error` event is emitted before the stream closes; the
 * source is also closed when a terminal event arrives (belt-and-braces vs.
 * backend close timing).
 */

export type JobEventStatus = "running" | "done" | "error";

export class JobStreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JobStreamError";
  }
}

export interface SubscribeJobOptions {
  /** Called on `status` events (e.g. "running"). Never on heartbeats. */
  onStatus?: (status: string) => void;
  /** Abort the subscription (closes the EventSource). */
  signal?: AbortSignal;
}

export function subscribeJob<T = unknown>(
  jobId: string,
  { onStatus, signal }: SubscribeJobOptions = {},
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const url = `/api/jobs/${encodeURIComponent(jobId)}/events`;
    const source = new EventSource(url);
    let settled = false;

    const cleanup = () => {
      source.close();
      signal?.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(new JobStreamError("Job stream aborted."));
    };

    signal?.addEventListener("abort", onAbort);

    // Terminal event: payload is the job result (same shape as the sync
    // response body, e.g. {ideas, run_id} for kind=ideas).
    source.addEventListener("done", (event) => {
      if (settled) return;
      settled = true;
      cleanup();
      try {
        resolve(JSON.parse((event as MessageEvent).data) as T);
      } catch {
        reject(new JobStreamError("Malformed job result payload."));
      }
    });

    source.addEventListener("error", (event) => {
      if (settled) return;
      // Backend terminal `error` event vs. EventSource's own error event:
      // MessageEvent has a `data` field, the native one does not.
      if (typeof (event as MessageEvent).data === "string") {
        settled = true;
        cleanup();
        let message = "Job failed.";
        try {
          const parsed = JSON.parse((event as MessageEvent).data) as { message?: string; detail?: string };
          message = parsed.message ?? parsed.detail ?? message;
        } catch {
          message = (event as MessageEvent).data || message;
        }
        reject(new JobStreamError(message));
      }
      // Native EventSource reconnect/error: fall through — the backend
      // replays the terminal event on reconnect if the job already finished.
    });

    source.addEventListener("status", (event) => {
      if (settled) return;
      try {
        const parsed = JSON.parse((event as MessageEvent).data) as { status?: string };
        if (parsed.status) onStatus?.(parsed.status);
      } catch {
        // Ignore malformed status frames.
      }
    });

    // `heartbeat` events are intentional no-ops (keep-alive only).
  });
}
