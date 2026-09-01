import { useSyncExternalStore } from "react";
import {
  getAuthState,
  getProviders,
  signIn,
  signOut,
  subscribeAuth,
  type AuthState,
  type AuthUser,
} from "../lib/auth";

/** React binding for the session-backed auth state (see lib/auth.ts). */
export function useAuth(): {
  status: AuthState["status"];
  user: AuthUser | null;
  signIn: (provider: string, next?: string) => void;
  signOut: () => Promise<void>;
  getProviders: () => Promise<string[]>;
} {
  const s = useSyncExternalStore(subscribeAuth, getAuthState, getAuthState);
  return { status: s.status, user: s.user, signIn, signOut, getProviders };
}
