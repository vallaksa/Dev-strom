import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useDemoMode } from "../hooks/useDemoMode";
import { useIdeaGeneration } from "../hooks/useIdeaGeneration";
import "./AppShell.css";

const NAV_ITEMS = [
  { to: "/", label: "Ideas", index: "I" },
  { to: "/cartographer", label: "Cartographer", index: "II" },
  { to: "/advisor", label: "Advisor", index: "III" },
  { to: "/history", label: "History", index: "IV" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { demoMode, forced, setDemoMode } = useDemoMode();
  const [generation] = useIdeaGeneration();
  const generating = generation.status === "loading";

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
                <span className="app-shell__nav-index">{item.index}</span>
                {item.to === "/" && generating ? "Generating…" : item.label}
              </NavLink>
            ))}
          </nav>

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
        </div>
      </header>

      <main className="app-shell__main">{children}</main>

      <footer className="app-shell__footer">
        <span className="mono-label">Dev-Strom &mdash; Idea Generator &amp; Project Cartographer</span>
      </footer>
    </div>
  );
}
