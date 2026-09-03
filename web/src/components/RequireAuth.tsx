import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { LoadingState } from "./StateBlocks";

/** Gate for the app routes: renders children only for a live session,
 *  otherwise sends the visitor to /login with a return path. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div style={{ padding: "25vh 0", display: "flex", justifyContent: "center" }}>
        <LoadingState label="Checking your session" />
      </div>
    );
  }

  if (status === "anonymous") {
    const next = location.pathname + location.search;
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />;
  }

  return <>{children}</>;
}
