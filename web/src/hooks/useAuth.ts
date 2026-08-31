import { useSyncExternalStore } from "react";
import { getUser, signIn, signOut, subscribeAuth, type AuthUser } from "../lib/auth";

/** React binding for the client-side auth seam (see lib/auth.ts). */
export function useAuth(): {
  user: AuthUser | null;
  signIn: (email: string) => Promise<AuthUser>;
  signOut: () => void;
} {
  const user = useSyncExternalStore(subscribeAuth, getUser, getUser);
  return { user, signIn, signOut };
}
