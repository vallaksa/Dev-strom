import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useDemoMode } from "../hooks/useDemoMode";
import { useIdeaGeneration } from "../hooks/useIdeaGeneration";
import { useTheme } from "../hooks/useTheme";
import "./AppShell.css";

const NAV_ITEMS = [
  { to: "/", label: "Ideas" },
  { to: "/advisor", label: "Repository Intelligence" },
  { to: "/history", label: "History" },
];

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="4" fill="currentColor" />
      <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
      </g>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
      <path
        d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { demoMode, forced, setDemoMode } = useDemoMode();
  const { resolved, toggleTheme } = useTheme();
  const [generation] = useIdeaGeneration();
  const generating = generation.status === "loading";
  const isDark = resolved === "dark";

  return (
    <div className="app-shell">
      <header className="app-shell__header">
        <div className="app-shell__header-inner">
          <NavLink to="/" className="app-shell__wordmark">
            <span className="app-shell__wordmark-mark">DS</span>
            <span className="app-shell__wordmark-text">
              Dev&#8209;Strom
            </span>
          </NavLink>

          <nav className="app-shell__nav">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  "app-shell__nav-link" +
                  (isActive ? " is-active" : "") +
                  (item.to === "/" && generating ? " is-busy" : "")
                }
              >
                {item.to === "/" && generating ? "Generating…" : item.label}
              </NavLink>
            ))}
          </nav>

          <div className="app-shell__controls">
            <button
              type="button"
              className={"demo-toggle" + (demoMode ? " is-on" : "")}
              onClick={() => setDemoMode(!demoMode)}
              disabled={forced}
              title={
                forced
                  ? "Demo mode is forced on via VITE_DEMO_MODE"
                  : "Toggle demo mode (uses local fixtures instead of the live API)"
              }
            >
              <span className="demo-toggle__dot" />
              {demoMode ? "Demo Mode: On" : "Demo Mode: Off"}
            </button>

            <button
              type="button"
              className="theme-toggle"
              data-state={isDark ? "dark" : "light"}
              onClick={toggleTheme}
              role="switch"
              aria-checked={isDark}
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
              title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            >
              <span className="theme-toggle__thumb">
                {isDark ? <MoonIcon /> : <SunIcon />}
              </span>
            </button>
          </div>
        </div>
      </header>

      <main className="app-shell__main">{children}</main>

      <footer className="app-shell__footer">
        <span className="mono-label">Dev-Strom &mdash; Idea Generator &amp; Repository Intelligence</span>
      </footer>
    </div>
  );
}
