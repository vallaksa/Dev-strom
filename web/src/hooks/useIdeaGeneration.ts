import { useCallback, useSyncExternalStore } from "react";
import { postIdeas } from "../api/ideas";
import { ApiError } from "../api/client";
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
  | { status: "success"; batches: IdeaBatch[] };

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

export async function generateIdeas(body: IdeasRequest): Promise<IdeasResponse | undefined> {
  const id = ++requestId;
  const priorBatches = state.status === "success" ? state.batches : [];
  state = { status: "loading" };
  emit();
  try {
    const data = await postIdeas(body);
    if (requestId === id) {
      const batch = appendBatch(data);
      state = { status: "success", batches: [...priorBatches, batch] };
      emit();
    }
    return data;
  } catch (err) {
    if (requestId === id) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      state =
        priorBatches.length > 0
          ? { status: "success", batches: priorBatches }
          : { status: "error", error: message };
      emit();
    }
    return undefined;
  }
}

export function useIdeaGeneration(): [
  GenerationState,
  (body: IdeasRequest) => Promise<IdeasResponse | undefined>,
] {
  const current = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const run = useCallback((body: IdeasRequest) => generateIdeas(body), []);
  return [current, run];
}
