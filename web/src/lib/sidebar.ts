/**
 * Sidebar collapsed/expanded state, persisted per browser. On desktop the
 * sidebar collapses to a narrow icon rail; on mobile it slides off-canvas
 * (the same flag drives both — the CSS decides what "collapsed" looks like).
 */

const STORAGE_KEY = "devstrom.sidebarCollapsed";

type Listener = () => void;
const listeners = new Set<Listener>();

function readStored(): boolean {
  if (typeof window === "undefined") return false;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "true") return true;
  if (stored === "false") return false;
  // No stored preference: start collapsed on narrow viewports, open otherwise.
  return window.matchMedia("(max-width: 900px)").matches;
}

let collapsed = readStored();

export function isSidebarCollapsed(): boolean {
  return collapsed;
}

export function setSidebarCollapsed(next: boolean): void {
  collapsed = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, String(next));
  } catch {
    // ignore (private browsing / storage disabled)
  }
  listeners.forEach((l) => l());
}

export function toggleSidebar(): void {
  setSidebarCollapsed(!collapsed);
}

export function subscribeSidebar(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
