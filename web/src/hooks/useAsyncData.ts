import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import type { AsyncState } from "./useAsyncAction";

/**
 * Runs an async loader on mount (and whenever `deps` changes), tracking
 * idle/loading/success/error state. Use for GET-on-load pages (History,
 * run detail, etc). For on-demand submits (forms), use useAsyncAction.
 */
export function useAsyncData<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  const requestId = useRef(0);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const id = ++requestId.current;
    setState({ status: "loading" });
    loader()
      .then((data) => {
        if (!cancelled && requestId.current === id) setState({ status: "success", data });
      })
      .catch((err) => {
        if (!cancelled && requestId.current === id) {
          const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
          setState({ status: "error", error: message });
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) } as AsyncState<T> & { reload: () => void };
}
