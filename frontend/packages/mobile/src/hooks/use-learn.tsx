// Learn-progress context, ported from ../nafa-iq-zenith/src/hooks/use-learn.tsx.
// Persistence moves from web localStorage to AsyncStorage; same storage key,
// shape, and default seed so progress matches the web app.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

export type LessonStatus = "complete" | "in-progress" | "not-started";

type LearnState = {
  xp: number;
  completion: Record<string, LessonStatus>;
  bookmarks: string[];
};

const STORAGE_KEY = "nafaiq-learn-progress-v1";
export const XP_GOAL = 500;

const DEFAULT_STATE: LearnState = {
  xp: 240,
  completion: { candlestick: "complete", "stop-loss": "complete", rsi: "in-progress" },
  bookmarks: [],
};

type LearnContextValue = {
  xp: number;
  bookmarks: string[];
  ready: boolean;
  statusOf: (id: string) => LessonStatus;
  completeLesson: (id: string, xpGain: number) => void;
  toggleBookmark: (id: string) => void;
  pathProgress: (lessonIds: string[]) => number;
};

const LearnContext = createContext<LearnContextValue | undefined>(undefined);

export function LearnProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LearnState>(DEFAULT_STATE);
  const [ready, setReady] = useState(false);
  const hydrated = useRef(false);

  // Hydrate once from AsyncStorage.
  useEffect(() => {
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) setState({ ...DEFAULT_STATE, ...JSON.parse(raw) });
      } catch {
        // ignore corrupt storage — fall back to defaults
      } finally {
        hydrated.current = true;
        setReady(true);
      }
    })();
  }, []);

  // Persist on change (after hydration).
  useEffect(() => {
    if (hydrated.current) AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(state)).catch(() => {});
  }, [state]);

  const statusOf = (id: string): LessonStatus => state.completion[id] ?? "not-started";

  const completeLesson = (id: string, xpGain: number) =>
    setState((s) => {
      if (s.completion[id] === "complete") return s;
      return {
        ...s,
        xp: s.xp + xpGain,
        completion: { ...s.completion, [id]: "complete" },
      };
    });

  const toggleBookmark = (id: string) =>
    setState((s) => ({
      ...s,
      bookmarks: s.bookmarks.includes(id)
        ? s.bookmarks.filter((b) => b !== id)
        : [...s.bookmarks, id],
    }));

  const pathProgress = (lessonIds: string[]) => {
    if (lessonIds.length === 0) return 0;
    const done = lessonIds.filter((id) => state.completion[id] === "complete").length;
    return done / lessonIds.length;
  };

  return (
    <LearnContext.Provider
      value={{
        xp: state.xp,
        bookmarks: state.bookmarks,
        ready,
        statusOf,
        completeLesson,
        toggleBookmark,
        pathProgress,
      }}
    >
      {children}
    </LearnContext.Provider>
  );
}

export function useLearn() {
  const ctx = useContext(LearnContext);
  if (!ctx) throw new Error("useLearn must be used within LearnProvider");
  return ctx;
}
