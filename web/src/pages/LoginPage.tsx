import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import "./LoginPage.css";

const PROVIDER_LABEL: Record<string, string> = {
  google: "Continue with Google",
  github: "Continue with GitHub",
};

const ERROR_MESSAGE: Record<string, string> = {
  bad_state: "That sign-in attempt expired or was tampered with. Try again.",
  oauth_failed: "The provider rejected the sign-in. Try again.",
  email_taken: "That email is already registered with a different provider.",
  server_error: "Something went wrong on our end. Try again.",
  access_denied: "Sign-in was cancelled.",
};

function GoogleGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <path d="M21.6 12.2c0-.7-.06-1.4-.18-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3Z" fill="#4285F4" />
      <path d="M12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.7-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22Z" fill="#34A853" />
      <path d="M6.4 14c-.2-.6-.3-1.3-.3-2s.1-1.4.3-2V7.4H3.1A10 10 0 0 0 2 12c0 1.6.4 3.2 1.1 4.6L6.4 14Z" fill="#FBBC05" />
      <path d="M12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.9C17 2.9 14.7 2 12 2A10 10 0 0 0 3.1 7.4L6.4 10c.8-2.4 3-4.1 5.6-4.1Z" fill="#EA4335" />
    </svg>
  );
}

function GithubGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="currentColor">
      <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48l-.01-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.1-1.46-1.1-1.46-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.89 1.52 2.34 1.08 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85l-.01 2.75c0 .27.18.58.69.48A10 10 0 0 0 12 2Z" />
    </svg>
  );
}

export function LoginPage() {
  const { status, signIn, getProviders } = useAuth();
  const [params] = useSearchParams();
  const [providers, setProviders] = useState<string[] | null>(null);
  const next = params.get("next") || "/ideas";
  const error = params.get("error");

  useEffect(() => {
    getProviders().then(setProviders);
  }, [getProviders]);

  if (status === "authenticated") {
    window.location.replace(next.startsWith("/") ? next : "/ideas");
    return null;
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <Link to="/" className="login-card__brand">
          <img src="/logo-mark.svg" alt="" width="30" height="30" />
          <span>Dev&#8209;Strom</span>
        </Link>
        <h1 className="login-card__title">Sign in</h1>
        <p className="login-card__lede">
          Dev-Strom keeps your ideas and repo analyses tied to your account.
        </p>

        {error && (
          <p className="login-card__error">{ERROR_MESSAGE[error] ?? "Sign-in failed. Try again."}</p>
        )}

        <div className="login-card__providers">
          {providers === null && <span className="mono-label">Loading…</span>}
          {providers?.length === 0 && (
            <p className="login-card__error">
              No sign-in providers are configured on this server.
            </p>
          )}
          {providers?.map((p) => (
            <button
              key={p}
              type="button"
              className="btn btn-secondary login-card__provider"
              onClick={() => signIn(p, next)}
            >
              {p === "google" ? <GoogleGlyph /> : <GithubGlyph />}
              {PROVIDER_LABEL[p] ?? `Continue with ${p}`}
            </button>
          ))}
        </div>

        <Link to="/" className="login-card__back mono-label">
          &larr; Back to home
        </Link>
      </div>
    </div>
  );
}
