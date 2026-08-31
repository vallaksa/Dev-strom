import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useSidebar } from "../hooks/useSidebar";
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
      <Sidebar />

      <div className="app-shell__body">
        <header className="app-shell__topbar">
          <button
            type="button"
            className="app-shell__menu-btn"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Open sidebar" : "Close sidebar"}
            aria-expanded={!collapsed}
          >
            <MenuIcon />
          </button>
          <NavLink to="/" className="app-shell__wordmark">
            <span className="app-shell__wordmark-mark">DS</span>
            <span className="app-shell__wordmark-text">Dev&#8209;Strom</span>
          </NavLink>
        </header>

        <main className="app-shell__main">{children}</main>
      </div>
    </div>
  );
}
