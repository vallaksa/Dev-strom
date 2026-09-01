/**
 * A bare signal the sidebar run list subscribes to. Anything that creates a
 * new run (idea generation, repo analysis) calls `notifyRunsChanged()` so the
 * sidebar refetches `/history` + `/analyses` without a full navigation.
 */

type Listener = () => void;
const listeners = new Set<Listener>();

let revision = 0;

/** Monotonic counter — feed it into a hook's dep array to force a refetch. */
export function getRunsRevision(): number {
  return revision;
}

export function notifyRunsChanged(): void {
  revision += 1;
  listeners.forEach((l) => l());
}

export function subscribeRuns(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
