import { useSyncExternalStore } from "react";
import { isDemoMode, isDemoModeForced, setDemoMode, subscribeDemoMode } from "../lib/demoMode";

/** React binding for the demo-mode flag (see lib/demoMode.ts). */
export function useDemoMode(): {
  demoMode: boolean;
  forced: boolean;
  setDemoMode: (next: boolean) => void;
} {
  const demoMode = useSyncExternalStore(subscribeDemoMode, isDemoMode, isDemoMode);
  return { demoMode, forced: isDemoModeForced(), setDemoMode };
}
