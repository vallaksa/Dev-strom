/**
 * SSE job stream client — mirrors app/services/sse.py.
 *
 * `subscribeJob` opens an EventSource on GET /api/jobs/{job_id}/events and
 * resolves with the job's terminal result. The backend frames:
 *
 *   event: status     data: {"status": "running"}
 *   event: heartbeat  data: (ignored)
 *   event: done       data: { ...job.result... }
 *   event: error      data: {"error": ...}
 *
 * Note the terminal error key is `error` — that is what app/services/sse.py
 * emits and what both Python test suites assert on. Reading `message` here
 * instead is how the backend's real failure reason used to get replaced by a
 * generic "Job failed." on its way to the user.
 *
 * Native EventSource `error` events have no `data`. After a bounded number
 * of those, we close the stream and poll GET /jobs/{id}: if the job already
 * finished we resolve/reject from that row; otherwise we reject so the UI
 * cannot sit in `loading` forever.
 */

export type JobEventStatus = "running" | "done" | "error";

export class JobStreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JobStreamError";
  }
}

export interface JobPollRecord {
  job_id?: string;
  kind?: string;
  status?: string;
  result?: unknown;
  error?: string | null;
}

export interface SubscribeJobOptions {
  /** Called on `status` events (e.g. "running"). Never on heartbeats. */
  onStatus?: (status: string) => void;
  /** Abort the subscription (closes the EventSource). */
  signal?: AbortSignal;
  /** Injectable EventSource (tests). Defaults to the browser global. */
  eventSourceCtor?: { new (url: string): EventSource };
  /** Native EventSource errors (no `data`) before we poll/reject. Default 3. */
  maxNativeErrors?: number;
  /** Injectable JSON poll used after bounded native errors. */
  fetchJob?: (jobId: string) => Promise<JobPollRecord>;
}

const DEFAULT_MAX_NATIVE_ERRORS = 3;

function parseNamedError(raw: string): string {
  let message = "Job failed.";
  try {
    const parsed = JSON.parse(raw) as {
      error?: string;
      message?: string;
      detail?: string;
    };
    message = parsed.error ?? parsed.message ?? parsed.detail ?? message;
  } catch {
    message = raw || message;
  }
  return message;
}

export function subscribeJob<T = unknown>(
  jobId: string,
  { onStatus, signal, eventSourceCtor, maxNativeErrors, fetchJob }: SubscribeJobOptions = {},
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const url = `/api/jobs/${encodeURIComponent(jobId)}/events`;
    const Ctor = eventSourceCtor ?? EventSource;
    const source = new Ctor(url);
    const nativeErrorBudget = maxNativeErrors ?? DEFAULT_MAX_NATIVE_ERRORS;
    const pollJob =
      fetchJob ??
      (async (id: string) => {
        const { apiClient } = await import("./client");
        return apiClient.get<JobPollRecord>(`/jobs/${encodeURIComponent(id)}`);
      });
    let settled = false;
    let nativeErrors = 0;

    const cleanup = () => {
      source.close();
      signal?.removeEventListener("abort", onAbort);
    };
    const settleReject = (err: Error) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(err);
    };
    const onAbort = () => {
      settleReject(new JobStreamError("Job stream aborted."));
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
        settleReject(new JobStreamError(parseNamedError((event as MessageEvent).data)));
        return;
      }

      nativeErrors += 1;
      if (nativeErrors < nativeErrorBudget) {
        // Leave the EventSource open so the browser can reconnect; the
        // backend replays a terminal event if the job already finished.
        return;
      }

      source.close();
      void pollJob(jobId)
        .then((record) => {
          if (settled) return;
          if (record.status === "done") {
            settled = true;
            cleanup();
            resolve((record.result ?? {}) as T);
            return;
          }
          if (record.status === "error") {
            settleReject(new JobStreamError(record.error || "Job failed."));
            return;
          }
          settleReject(
            new JobStreamError("Job stream disconnected before the job finished."),
          );
        })
        .catch(() => {
          settleReject(
            new JobStreamError("Job stream disconnected before the job finished."),
          );
        });
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
