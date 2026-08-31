import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useIdeaGeneration } from "../../hooks/useIdeaGeneration";
import { useSidebar } from "../../hooks/useSidebar";
import { ProfileBlock } from "./ProfileBlock";
import { RunList } from "./RunList";
import "./Sidebar.css";

const NEW_ACTIONS = [
  { to: "/", label: "New Ideas", end: true },
  { to: "/advisor", label: "New Analysis", end: false },
];

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function Sidebar() {
  const { collapsed, setSidebarCollapsed } = useSidebar();
  const [generation] = useIdeaGeneration();
  const generating = generation.status === "loading";
  const { pathname } = useLocation();

  // On mobile the sidebar is a drawer over the content — close it after a nav.
  useEffect(() => {
    if (window.matchMedia("(max-width: 900px)").matches) {
      setSidebarCollapsed(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <>
      {!collapsed && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarCollapsed(true)}
          role="presentation"
        />
      )}
      <aside className={"sidebar" + (collapsed ? " is-collapsed" : "")}>
        <nav className="sidebar__actions">
          {NEW_ACTIONS.map((action) => (
            <NavLink
              key={action.to}
              to={action.to}
              end={action.end}
              className={({ isActive }) =>
                "sidebar__action" + (isActive ? " is-active" : "")
              }
              title={action.label}
            >
              <span className="sidebar__action-icon">
                <PlusIcon />
              </span>
              <span className="sidebar__action-label">
                {action.to === "/" && generating ? "Generating…" : action.label}
              </span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__runs">
          <RunList />
        </div>

        <ProfileBlock collapsed={collapsed} />
      </aside>
    </>
  );
}
