import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { LessonStatus } from "@/lib/learn/data";

const STORAGE_KEY = "nafaiq-learn-progress-v1";
const BASE_XP = 240;

interface LearnState {
  xp: number;
  completion: Record<string, LessonStatus>;
  bookmarks: string[];
}

const DEFAULT_STATE: LearnState = {
  xp: BASE_XP,
  completion: {
    candlestick: "complete",
    "stop-loss": "complete",
    rsi: "in-progress",
  },
  bookmarks: [],
};

interface LearnContextValue extends LearnState {
  statusOf: (id: string) => LessonStatus;
  completeLesson: (id: string, xpGain: number) => void;
  toggleBookmark: (id: string) => void;
  pathProgress: (lessonIds: string[]) => number;
}

const LearnContext = createContext<LearnContextValue | null>(null);

function load(): LearnState {
  if (typeof window === "undefined") return DEFAULT_STATE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw) as Partial<LearnState>;
    return {
      xp: typeof parsed.xp === "number" ? parsed.xp : DEFAULT_STATE.xp,
      completion: { ...DEFAULT_STATE.completion, ...(parsed.completion ?? {}) },
      bookmarks: Array.isArray(parsed.bookmarks) ? parsed.bookmarks : [],
    };
  } catch {
    return DEFAULT_STATE;
  }
}

export function LearnProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LearnState>(DEFAULT_STATE);

  useEffect(() => {
    setState(load());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const statusOf = useCallback(
    (id: string): LessonStatus => state.completion[id] ?? "not-started",
    [state.completion],
  );

  const completeLesson = useCallback((id: string, xpGain: number) => {
    setState((prev) => {
      const already = prev.completion[id] === "complete";
      return {
        ...prev,
        completion: { ...prev.completion, [id]: "complete" },
        xp: already ? prev.xp : prev.xp + xpGain,
      };
    });
  }, []);

  const toggleBookmark = useCallback((id: string) => {
    setState((prev) => ({
      ...prev,
      bookmarks: prev.bookmarks.includes(id)
        ? prev.bookmarks.filter((b) => b !== id)
        : [...prev.bookmarks, id],
    }));
  }, []);

  const pathProgress = useCallback(
    (lessonIds: string[]) => {
      if (lessonIds.length === 0) return 0;
      const done = lessonIds.filter((l) => state.completion[l] === "complete").length;
      return Math.round((done / lessonIds.length) * 100);
    },
    [state.completion],
  );

  const value = useMemo<LearnContextValue>(
    () => ({ ...state, statusOf, completeLesson, toggleBookmark, pathProgress }),
    [state, statusOf, completeLesson, toggleBookmark, pathProgress],
  );

  return <LearnContext.Provider value={value}>{children}</LearnContext.Provider>;
}

export function useLearn(): LearnContextValue {
  const ctx = useContext(LearnContext);
  if (!ctx) throw new Error("useLearn must be used within LearnProvider");
  return ctx;
}
