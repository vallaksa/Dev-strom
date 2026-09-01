/**
 * Client-side auth seam.
 *
 * The Dev-Strom backend has no auth yet — every request runs as
 * ANONYMOUS_USER_ID. This module is the single place a real flow plugs in:
 * replace the bodies of `signIn` / `signOut` / `restore` with calls to the
 * eventual `/auth/*` endpoints and the rest of the UI keeps working.
 *
 * Until then it keeps a mock session in localStorage so the profile UI is
 * fully exercisable.
 */

export interface AuthUser {
  id: string;
  name: string;
  email: string;
}

const STORAGE_KEY = "devstrom.auth";

type Listener = () => void;
const listeners = new Set<Listener>();

function readStored(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AuthUser>;
    if (parsed && parsed.id && parsed.email && parsed.name) {
      return parsed as AuthUser;
    }
  } catch {
    // ignore malformed / unavailable storage
  }
  return null;
}

let currentUser: AuthUser | null = readStored();

export function getUser(): AuthUser | null {
  return currentUser;
}

function persist(user: AuthUser | null): void {
  try {
    if (user) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore (private browsing / storage disabled)
  }
}

function nameFromEmail(email: string): string {
  const local = email.split("@")[0] ?? email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ") || email;
}

/**
 * TODO(auth): replace with `POST /auth/session { email }` (magic-link or
 * password) and hydrate `currentUser` from the response.
 */
export async function signIn(email: string): Promise<AuthUser> {
  const trimmed = email.trim();
  const user: AuthUser = {
    id: `local:${trimmed.toLowerCase()}`,
    name: nameFromEmail(trimmed),
    email: trimmed,
  };
  currentUser = user;
  persist(user);
  listeners.forEach((l) => l());
  return user;
}

/** TODO(auth): replace with `DELETE /auth/session`. */
export function signOut(): void {
  currentUser = null;
  persist(null);
  listeners.forEach((l) => l());
}

export function subscribeAuth(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
