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

/** Fetch the current session. Idempotent — concurrent callers share one request.
 *  A transient network error retries once and, if still failing, leaves the
 *  prior state alone rather than falsely signing the user out. Only an actual
 *  HTTP response settles the state. */
export function refreshAuth(): Promise<void> {
  if (inflight) return inflight;
  inflight = (async () => {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const res = await fetch("/api/auth/me", { credentials: "include" });
        state = res.ok
          ? { status: "authenticated", user: (await res.json()) as AuthUser }
          : { status: "anonymous", user: null };
        break;
      } catch {
        if (attempt === 1 && state.status === "loading") {
          state = { status: "anonymous", user: null };
        }
        await new Promise((r) => setTimeout(r, 400));
      }
    }
    emit();
    inflight = null;
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
