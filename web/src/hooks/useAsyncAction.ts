import { useCallback, useRef, useState } from "react";
import { ApiError } from "../api/client";

export type AsyncState<T> =
  | { status: "idle"; data?: undefined; error?: undefined }
  | { status: "loading"; data?: undefined; error?: undefined }
  | { status: "success"; data: T; error?: undefined }
  | { status: "error"; data?: undefined; error: string };

/**
 * Wraps an on-demand async call (e.g. a form submit) with idle/loading/
 * success/error state, guarding against a stale response overwriting a
 * newer request if the caller fires multiple times in quick succession.
 */
export function useAsyncAction<Args extends unknown[], T>(
  fn: (...args: Args) => Promise<T>,
): [AsyncState<T>, (...args: Args) => Promise<T | undefined>, () => void] {
  const [state, setState] = useState<AsyncState<T>>({ status: "idle" });
  const requestId = useRef(0);

  const run = useCallback(
    async (...args: Args) => {
      const id = ++requestId.current;
      setState({ status: "loading" });
      try {
        const data = await fn(...args);
        if (requestId.current === id) setState({ status: "success", data });
        return data;
      } catch (err) {
        if (requestId.current === id) {
          const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
          setState({ status: "error", error: message });
        }
        return undefined;
      }
    },
    [fn],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return [state, run, reset];
}
