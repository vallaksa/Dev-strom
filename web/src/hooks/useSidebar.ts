import { useSyncExternalStore } from "react";
import {
  isSidebarCollapsed,
  setSidebarCollapsed,
  subscribeSidebar,
  toggleSidebar,
} from "../lib/sidebar";

/** React binding for the sidebar collapsed flag (see lib/sidebar.ts). */
export function useSidebar(): {
  collapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (next: boolean) => void;
} {
  const collapsed = useSyncExternalStore(
    subscribeSidebar,
    isSidebarCollapsed,
    isSidebarCollapsed,
  );
  return { collapsed, toggleSidebar, setSidebarCollapsed };
}
