import { useSyncExternalStore, useCallback } from "react";

export type LandingTheme = "dark" | "light";

const STORAGE_KEY = "nafaiq-landing-theme";
const listeners = new Set<() => void>();
let current: LandingTheme = readStored();

function readStored(): LandingTheme {
  if (typeof window === "undefined") return "dark";
  const v = window.localStorage.getItem(STORAGE_KEY);
  return v === "light" ? "light" : "dark";
}

function setStore(theme: LandingTheme) {
  current = theme;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, theme);
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/**
 * Landing page theme (dark/light) — independent from the app theme.
 * Persisted to localStorage. Defaults to dark.
 */
export function useLandingTheme() {
  const theme = useSyncExternalStore(
    subscribe,
    () => current,
    () => "dark" as LandingTheme,
  );

  const setTheme = useCallback((t: LandingTheme) => setStore(t), []);
  const toggleTheme = useCallback(
    () => setStore(current === "dark" ? "light" : "dark"),
    [],
  );

  return { theme, setTheme, toggleTheme };
}
