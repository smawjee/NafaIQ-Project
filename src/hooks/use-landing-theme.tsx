import {
  createContext,
  useCallback,
  useContext,
  useState,
} from "react";

export type LandingTheme = "dark" | "light";

const STORAGE_KEY = "nafaiq-landing-theme";

function readStored(): LandingTheme {
  if (typeof window === "undefined") return "dark";
  return window.localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
}

interface ThemeContextValue {
  theme: LandingTheme;
  setTheme: (t: LandingTheme) => void;
  toggleTheme: () => void;
}

const LandingThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  setTheme: () => {},
  toggleTheme: () => {},
});

function useStoredTheme(): ThemeContextValue {
  const [theme, setThemeState] = useState<LandingTheme>(readStored);

  const setTheme = useCallback((t: LandingTheme) => {
    setThemeState(t);
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

  return { theme, setTheme, toggleTheme };
}

export function LandingThemeProvider({ children }: { children: React.ReactNode }) {
  const value = useStoredTheme();
  return (
    <LandingThemeContext.Provider value={value}>
      {children}
    </LandingThemeContext.Provider>
  );
}

export function useLandingTheme() {
  return useContext(LandingThemeContext);
}
