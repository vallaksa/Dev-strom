import { useSyncExternalStore } from "react";
import {
  getResolvedTheme,
  getThemePreference,
  setThemePreference,
  subscribeTheme,
  toggleTheme,
  type ResolvedTheme,
  type ThemePreference,
} from "../lib/theme";

/** React binding for the colour-theme preference (see lib/theme.ts). */
export function useTheme(): {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setThemePreference: (next: ThemePreference) => void;
  toggleTheme: () => void;
} {
  const preference = useSyncExternalStore(
    subscribeTheme,
    getThemePreference,
    getThemePreference,
  );
  const resolved = useSyncExternalStore(
    subscribeTheme,
    getResolvedTheme,
    getResolvedTheme,
  );
  return { preference, resolved, setThemePreference, toggleTheme };
}
