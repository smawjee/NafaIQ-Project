import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type LandingTheme = "dark" | "light";

const STORAGE_KEY = "nafaiq-landing-theme";
const LIGHT_CLASSES = ["theme-light", "landing-light"] as const;

function readStored(): LandingTheme {
  if (typeof window === "undefined") return "dark";
  return window.localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
}

function applyToDocument(theme: LandingTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  for (const c of LIGHT_CLASSES) {
    root.classList.toggle(c, theme === "light");
  }
}

interface ThemeContextValue {
  theme: LandingTheme;
  setTheme: (t: LandingTheme) => void;
  toggleTheme: () => void;
  hydrated: boolean;
}

const LandingThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  setTheme: () => {},
  toggleTheme: () => {},
  hydrated: false,
});

function useStoredTheme(): ThemeContextValue {
  const [theme, setThemeState] = useState<LandingTheme>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setThemeState(readStored());
    setHydrated(true);
  }, []);

  const setTheme = useCallback((t: LandingTheme) => {
    setThemeState(t);
    setHydrated(true);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, t);
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      if (typeof window !== "undefined") {
        window.localStorage.setItem(STORAGE_KEY, next);
      }
      return next;
    });
  }, []);

  return { theme, setTheme, toggleTheme, hydrated };
}

export function LandingThemeProvider({ children }: { children: React.ReactNode }) {
  const value = useStoredTheme();

  // Keep the html element's theme classes in sync with React state so the
  // toggle works from anywhere (landing, login, app) and survives navigation
  // without a flash. The pre-hydration inline script in __root.tsx handles
  // the first paint; this effect keeps subsequent toggles in lockstep.
  useEffect(() => {
    if (!value.hydrated) return;
    applyToDocument(value.theme);
  }, [value.hydrated, value.theme]);

  return <LandingThemeContext.Provider value={value}>{children}</LandingThemeContext.Provider>;
}

export function useLandingTheme() {
  return useContext(LandingThemeContext);
}
