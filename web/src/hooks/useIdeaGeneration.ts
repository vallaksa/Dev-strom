import { useCallback, useSyncExternalStore } from "react";
import { postIdeas } from "../api/ideas";
import { ApiError } from "../api/client";
import type { IdeasRequest, IdeasResponse } from "../api/types";
import type { AsyncState } from "./useAsyncAction";

type GenerationState = AsyncState<IdeasResponse>;

let state: GenerationState = { status: "idle" };
let requestId = 0;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): GenerationState {
  return state;
}

export async function generateIdeas(body: IdeasRequest): Promise<IdeasResponse | undefined> {
  const id = ++requestId;
  state = { status: "loading" };
  emit();
  try {
    const data = await postIdeas(body);
    if (requestId === id) {
      state = { status: "success", data };
      emit();
    }
    return data;
  } catch (err) {
    if (requestId === id) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      state = { status: "error", error: message };
      emit();
    }
    return undefined;
  }
}

export function useIdeaGeneration(): [GenerationState, (body: IdeasRequest) => Promise<IdeasResponse | undefined>] {
  const current = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const run = useCallback((body: IdeasRequest) => generateIdeas(body), []);
  return [current, run];
}
