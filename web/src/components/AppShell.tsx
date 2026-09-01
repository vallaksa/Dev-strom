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
        </div>

        <NavLink to="/" className="app-shell__wordmark">
          <img
            src="/logo-mark.svg"
            alt=""
            className="app-shell__wordmark-mark"
            width="24"
            height="24"
          />
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
