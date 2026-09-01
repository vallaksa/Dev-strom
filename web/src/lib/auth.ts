/**
 * Auth state, backed by the server session cookie.
 *
 * On load the app calls `refreshAuth()` once, which hits `GET /api/auth/me`.
 * Sign-in is a full-page redirect to the provider; the server sets the
 * `ds_session` cookie and bounces back. Sign-out clears it server-side.
 */

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  auth_provider: string;
}

export type AuthState =
  | { status: "loading"; user: null }
  | { status: "authenticated"; user: AuthUser }
  | { status: "anonymous"; user: null };

let state: AuthState = { status: "loading", user: null };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function getAuthState(): AuthState {
  return state;
}

export function subscribeAuth(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let inflight: Promise<void> | null = null;

/** Fetch the current session. Idempotent — concurrent callers share one request. */
export function refreshAuth(): Promise<void> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      if (res.ok) {
        state = { status: "authenticated", user: (await res.json()) as AuthUser };
      } else {
        state = { status: "anonymous", user: null };
      }
    } catch {
      state = { status: "anonymous", user: null };
    } finally {
      emit();
      inflight = null;
    }
  })();
  return inflight;
}

/** Providers the server has credentials for — the login page renders one button each. */
export async function getProviders(): Promise<string[]> {
  try {
    const res = await fetch("/api/auth/providers", { credentials: "include" });
    if (!res.ok) return [];
    return ((await res.json()) as { providers: string[] }).providers ?? [];
  } catch {
    return [];
  }
}

export function signIn(provider: string, next?: string): void {
  const q = next ? `?next=${encodeURIComponent(next)}` : "";
  window.location.href = `/api/auth/${provider}/login${q}`;
}

export async function signOut(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
  } catch {
    /* ignore — cookie may already be gone */
  }
  window.location.href = "/";
}
