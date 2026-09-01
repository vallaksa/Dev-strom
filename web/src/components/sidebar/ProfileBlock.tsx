import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useDemoMode } from "../../hooks/useDemoMode";
import { AuthModal } from "./AuthModal";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function ProfileBlock({ collapsed }: { collapsed: boolean }) {
  const { user, signOut } = useAuth();
  const { demoMode, forced, setDemoMode } = useDemoMode();
  const [menuOpen, setMenuOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const label = user ? user.name : "Guest";
  const sublabel = user ? user.email : "Not signed in";

  return (
    <div className="profile-block" ref={wrapRef}>
      <button
        type="button"
        className="profile-block__trigger"
        onClick={() => setMenuOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        title={user ? `${label} · ${sublabel}` : "Account & settings"}
      >
        <span className={"profile-block__avatar" + (user ? "" : " is-guest")}>
          {user ? initials(user.name) : "?"}
        </span>
        {!collapsed && (
          <span className="profile-block__id">
            <span className="profile-block__name">{label}</span>
            <span className="profile-block__sub">{sublabel}</span>
          </span>
        )}
      </button>

      {menuOpen && (
        <div className="profile-menu" role="menu">
          {user && (
            <div className="profile-menu__header">
              <span className="profile-block__name">{user.name}</span>
              <span className="profile-block__sub">{user.email}</span>
            </div>
          )}

          <button
            type="button"
            className="profile-menu__row"
            role="menuitemcheckbox"
            aria-checked={demoMode}
            onClick={() => !forced && setDemoMode(!demoMode)}
            disabled={forced}
            title={forced ? "Forced on via VITE_DEMO_MODE" : undefined}
          >
            <span>Demo mode</span>
            <span className={"profile-menu__pill" + (demoMode ? " is-on" : "")}>
              {demoMode ? "On" : "Off"}
            </span>
          </button>

          <div className="profile-menu__divider" />

          {user ? (
            <button
              type="button"
              className="profile-menu__row"
              role="menuitem"
              onClick={() => {
                signOut();
                setMenuOpen(false);
              }}
            >
              <span>Sign out</span>
            </button>
          ) : (
            <button
              type="button"
              className="profile-menu__row"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                setAuthOpen(true);
              }}
            >
              <span>Sign in</span>
            </button>
          )}
        </div>
      )}

      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} />}
    </div>
  );
}
