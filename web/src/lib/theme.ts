/**
 * Colour-theme preference (light / dark).
 *
 * Precedence:
 *   1. An explicit choice the visitor made via the header toggle, persisted
 *      to localStorage as "light" or "dark".
 *   2. Otherwise "system" — follow the OS `prefers-color-scheme`.
 *
 * The resolved theme is reflected on <html data-theme="…"> so tokens.css can
 * switch palettes. `applyTheme()` runs once at module load (and an inline
 * script in index.html does the same before first paint to avoid a flash).
 */

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "devstrom.theme";

type Listener = () => void;
const listeners = new Set<Listener>();

function readStored(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "light" || v === "dark" ? v : "system";
}

let preference: ThemePreference = readStored();

function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function getThemePreference(): ThemePreference {
  return preference;
}

export function getResolvedTheme(): ResolvedTheme {
  if (preference === "system") return systemPrefersDark() ? "dark" : "light";
  return preference;
}

function applyTheme(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (preference === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", preference);
  }
}

export function setThemePreference(next: ThemePreference): void {
  preference = next;
  try {
    if (next === "system") window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // ignore (private browsing / storage disabled)
  }
  applyTheme();
  listeners.forEach((l) => l());
}

/** Flip between light and dark, pinning the opposite of what's showing now. */
export function toggleTheme(): void {
  setThemePreference(getResolvedTheme() === "dark" ? "light" : "dark");
}

export function subscribeTheme(listener: Listener): () => void {
  listeners.add(listener);
  if (typeof window !== "undefined") {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (preference === "system") {
        applyTheme();
        listener();
      }
    };
    mq.addEventListener("change", onChange);
    return () => {
      listeners.delete(listener);
      mq.removeEventListener("change", onChange);
    };
  }
  return () => listeners.delete(listener);
}

applyTheme();
