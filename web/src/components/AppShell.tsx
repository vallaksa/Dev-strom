import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useSidebar } from "../hooks/useSidebar";
import { ThemeToggle } from "./ThemeToggle";
import { Sidebar } from "./sidebar/Sidebar";
import "./AppShell.css";

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M4 7h16M4 12h16M4 17h16"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ComposeIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
      <path
        d="M4 20h16M6.5 16.5 16 7l-2.5-2.5L4 14v2.5h2.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { collapsed, toggleSidebar } = useSidebar();

  return (
    <div className={"app-shell" + (collapsed ? " is-sidebar-collapsed" : "")}>
      <header className="app-shell__topbar">
        <div className="app-shell__topbar-left">
          <button
            type="button"
            className="app-shell__icon-btn"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Open menu" : "Close menu"}
            aria-expanded={!collapsed}
          >
            <MenuIcon />
          </button>
          <NavLink
            to="/"
            end
            className="app-shell__icon-btn"
            aria-label="New ideas"
            title="New ideas"
          >
            <ComposeIcon />
          </NavLink>
        </div>

        <NavLink to="/" className="app-shell__wordmark">
          <span className="app-shell__wordmark-mark">DS</span>
          <span className="app-shell__wordmark-text">Dev&#8209;Strom</span>
        </NavLink>

        <div className="app-shell__topbar-right">
          <ThemeToggle />
        </div>
      </header>

      <Sidebar />

      <div className="app-shell__body">
        <main className="app-shell__main">{children}</main>
      </div>
    </div>
  );
}
