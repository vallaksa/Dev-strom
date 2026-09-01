import { useSyncExternalStore } from "react";
import {
  getGroupsSnapshot,
  isSidebarCollapsed,
  setSidebarCollapsed,
  subscribeSidebar,
  toggleGroup,
  toggleSidebar,
  type RunGroup,
} from "../lib/sidebar";

/** React binding for sidebar UI state (see lib/sidebar.ts). */
export function useSidebar(): {
  collapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (next: boolean) => void;
  isGroupCollapsed: (group: RunGroup) => boolean;
  toggleGroup: (group: RunGroup) => void;
} {
  const collapsed = useSyncExternalStore(
    subscribeSidebar,
    isSidebarCollapsed,
    isSidebarCollapsed,
  );
  const groups = useSyncExternalStore(
    subscribeSidebar,
    getGroupsSnapshot,
    getGroupsSnapshot,
  );
  return {
    collapsed,
    toggleSidebar,
    setSidebarCollapsed,
    isGroupCollapsed: (group) => groups.has(group),
    toggleGroup,
  };
}
