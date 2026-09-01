/**
 * Sidebar UI state, persisted per browser:
 *   - `collapsed`: whether the whole side menu is open or hidden.
 *   - `collapsedGroups`: which run-list groups ("analyses" / "ideas") are
 *     folded shut.
 * Both share one listener set so any change re-renders the sidebar.
 */

const COLLAPSED_KEY = "devstrom.sidebarCollapsed";
const GROUPS_KEY = "devstrom.sidebarGroups";

export type RunGroup = "analyses" | "ideas";

type Listener = () => void;
const listeners = new Set<Listener>();
const emit = () => listeners.forEach((l) => l());

// ── open / closed ────────────────────────────────────────────────────────
function readCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  const stored = window.localStorage.getItem(COLLAPSED_KEY);
  if (stored === "true") return true;
  if (stored === "false") return false;
  // No stored preference: start collapsed on narrow viewports, open otherwise.
  return window.matchMedia("(max-width: 900px)").matches;
}

let collapsed = readCollapsed();

export function isSidebarCollapsed(): boolean {
  return collapsed;
}

export function setSidebarCollapsed(next: boolean): void {
  collapsed = next;
  try {
    window.localStorage.setItem(COLLAPSED_KEY, String(next));
  } catch {
    // ignore (private browsing / storage disabled)
  }
  emit();
}

export function toggleSidebar(): void {
  setSidebarCollapsed(!collapsed);
}

// ── run-list group folds ─────────────────────────────────────────────────
function readGroups(): Set<RunGroup> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(GROUPS_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as RunGroup[];
    return new Set(arr.filter((g) => g === "analyses" || g === "ideas"));
  } catch {
    return new Set();
  }
}

let collapsedGroups = readGroups();

export function isGroupCollapsed(group: RunGroup): boolean {
  return collapsedGroups.has(group);
}

export function toggleGroup(group: RunGroup): void {
  collapsedGroups = new Set(collapsedGroups);
  if (collapsedGroups.has(group)) collapsedGroups.delete(group);
  else collapsedGroups.add(group);
  try {
    window.localStorage.setItem(GROUPS_KEY, JSON.stringify([...collapsedGroups]));
  } catch {
    // ignore
  }
  emit();
}

/** A snapshot getter for useSyncExternalStore (stable identity per state). */
export function getGroupsSnapshot(): Set<RunGroup> {
  return collapsedGroups;
}

export function subscribeSidebar(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
