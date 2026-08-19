/**
 * Demo mode lets every page render and be fully interactive without a live
 * FastAPI backend — useful for review/demo environments where the backend
 * may not be running.
 *
 * Precedence:
 *   1. `VITE_DEMO_MODE=true` at build time forces demo mode on for every
 *      visitor (set this env var when deploying a backend-less preview).
 *   2. Otherwise, it's a runtime toggle persisted to localStorage, flipped
 *      from the AppShell's "Demo Mode" switch. Defaults to OFF so a normal
 *      dev/build against a real backend behaves as expected.
 */

const STORAGE_KEY = "devstrom.demoMode";
const BUILD_FORCED = String(import.meta.env.VITE_DEMO_MODE ?? "").toLowerCase() === "true";

type Listener = () => void;
const listeners = new Set<Listener>();

function readStored(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(STORAGE_KEY) === "true";
}

let current = BUILD_FORCED || readStored();

export function isDemoMode(): boolean {
  return BUILD_FORCED || current;
}

export function isDemoModeForced(): boolean {
  return BUILD_FORCED;
}

export function setDemoMode(next: boolean): void {
  if (BUILD_FORCED) return; // build-time flag wins; runtime toggle is a no-op
  current = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, String(next));
  } catch {
    // ignore (private browsing / storage disabled)
  }
  listeners.forEach((l) => l());
}

export function subscribeDemoMode(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
