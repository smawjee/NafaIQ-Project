// Learn Hub structural data, ported from ../nafa-iq-zenith/src/lib/learn-data.ts.
// LESSON_CONTENT (the full per-lesson bodies) is ported separately for the
// lesson-detail screen; this file holds the hub-level structures.
import { GLOSSARY } from "./finance-data";

export interface LearningPath {
  id: string;
  emoji: string;
  accent: string;
  title: string;
  description: string;
  lessonIds: string[];
  estMin: number;
}

export const LEARNING_PATHS: LearningPath[] = [
  { id: "psx-starter", emoji: "📊", accent: "#00d4aa", title: "PSX Investor Starter", description: "From zero to your first trade", lessonIds: ["candlestick", "psx", "stop-loss", "patterns"], estMin: 26 },
  { id: "technical", emoji: "📈", accent: "#8b5cf6", title: "Technical Analysis", description: "Charts, patterns, and indicators", lessonIds: ["rsi", "patterns", "heatmap"], estMin: 19 },
  { id: "islamic", emoji: "📿", accent: "#22c55e", title: "Islamic Finance", description: "Halal investing principles", lessonIds: ["halal", "dividend"], estMin: 15 },
  { id: "personal", emoji: "💰", accent: "#f59e0b", title: "Personal Finance", description: "Budget, save, and grow", lessonIds: ["budget", "dividend", "pe-ratio"], estMin: 18 },
];

export const LESSON_ID_BY_TITLE: Record<string, string> = {
  "What is a Candlestick?": "candlestick",
  "Understanding RSI": "rsi",
  "Sector Heatmap Guide": "heatmap",
  "What is a Stop-Loss?": "stop-loss",
  "Dividend Yield": "dividend",
  "5 Candle Patterns": "patterns",
  "50/30/20 Budget Rule": "budget",
  "How PSX Works": "psx",
  "Halal Investing & Islamic Finance": "halal",
  "Understanding P/E Ratio": "pe-ratio",
};

// Lessons that carry a video (drives the "Video + Article" badge).
export const VIDEO_LESSON_IDS = new Set<string>(["candlestick"]);

export interface Flashcard {
  front: string;
  ur: string;
  def: string;
}

export const FLASHCARDS: Flashcard[] = GLOSSARY.map((t) => ({ front: t.en, ur: t.ur, def: t.def }));

export function lessonOrder(): string[] {
  return Object.keys(LESSON_ID_BY_TITLE).map((title) => LESSON_ID_BY_TITLE[title]);
}

export function xpForScore(correct: number, total: number): number {
  if (correct >= total) return 50;
  if (correct >= Math.ceil(total * 0.66)) return 30;
  if (correct >= 1) return 10;
  return 0;
}
