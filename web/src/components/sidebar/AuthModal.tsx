import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../../hooks/useAuth";

/**
 * Placeholder sign-in. There is no auth backend yet — submitting creates a
 * local-only profile so the rest of the UI can be exercised. When real auth
 * lands, this form posts to `/auth/session` instead (see lib/auth.ts).
 */
export function AuthModal({ onClose }: { onClose: () => void }) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || busy) return;
    setBusy(true);
    try {
      await signIn(email);
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-modal__backdrop" onClick={onClose} role="presentation">
      <div
        className="auth-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="auth-modal-title" className="auth-modal__title">
          Sign in
        </h2>
        <p className="auth-modal__note">
          Sign-in isn&rsquo;t wired to a backend yet. This creates a local
          profile on this browser only.
        </p>
        <form className="auth-modal__form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="auth-email">Email</label>
            <input
              id="auth-email"
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus
              required
            />
          </div>
          <div className="auth-modal__actions">
            <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !email.trim()}>
              {busy ? "Signing in…" : "Continue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
