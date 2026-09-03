import { useCallback, useSyncExternalStore } from "react";
import { postIdeas } from "../api/ideas";
import { ApiError } from "../api/client";
import { JobStreamError } from "../api/jobs";
import { notifyRunsChanged } from "../lib/runsStore";
import type { Idea, IdeasRequest, IdeasResponse } from "../api/types";

export interface IdeaBatch {
  batchId: number;
  runId: string;
  label: string;
  ideas: Idea[];
}

type GenerationState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "success"; batches: IdeaBatch[]; appendError?: string };

export type GenerateIdeasOptions = {
  /** When true, append to prior batches; otherwise replace them. */
  append?: boolean;
};

let state: GenerationState = { status: "idle" };
let batchCounter = 0;
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

function batchLabel(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function appendBatch(data: IdeasResponse): IdeaBatch {
  batchCounter += 1;
  return {
    batchId: batchCounter,
    runId: data.run_id,
    label: `Batch ${batchCounter} · ${batchLabel()}`,
    ideas: data.ideas,
  };
}

export async function generateIdeas(
  body: IdeasRequest,
  options: GenerateIdeasOptions = {},
): Promise<IdeasResponse | undefined> {
  const append = options.append ?? false;
  const id = ++requestId;
  const priorBatches = append && state.status === "success" ? state.batches : [];
  if (!append) {
    batchCounter = 0;
  }
  state = { status: "loading" };
  emit();
  try {
    const data = await postIdeas(body);
    if (requestId === id) {
      const batch = appendBatch(data);
      state = { status: "success", batches: append ? [...priorBatches, batch] : [batch] };
      emit();
      notifyRunsChanged();
    }
    return data;
  } catch (err) {
    if (requestId === id) {
      // JobStreamError is not an ApiError — without it, every SSE-side
      // failure (the pipeline raising, a stream timing out) was flattened to
      // the generic fallback and the backend's actual reason never reached
      // the user.
      const message =
        err instanceof ApiError || err instanceof JobStreamError
          ? err.message
          : "Something went wrong. Please try again.";
      state =
        append && priorBatches.length > 0
          ? { status: "success", batches: priorBatches, appendError: message }
          : { status: "error", error: message };
      emit();
    }
    return undefined;
  }
}

export function useIdeaGeneration(): [
  GenerationState,
  (body: IdeasRequest, options?: GenerateIdeasOptions) => Promise<IdeasResponse | undefined>,
] {
  const current = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const run = useCallback(
    (body: IdeasRequest, options?: GenerateIdeasOptions) => generateIdeas(body, options),
    [],
  );
  return [current, run];
}
