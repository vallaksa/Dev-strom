import { useTheme } from "../hooks/useTheme";
import "./ThemeToggle.css";

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
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" fill="currentColor" />
    </svg>
  );
}

/** Sliding pill switch: sun-on-white-knob (light) ⇄ moon-on-dark-knob (dark). */
export function ThemeToggle() {
  const { resolved, toggleTheme } = useTheme();
  const isDark = resolved === "dark";

  return (
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
      <span className="theme-toggle__thumb">{isDark ? <MoonIcon /> : <SunIcon />}</span>
    </button>
  );
}
