import { STOCKS, type Signal } from "@/lib/data";

/** One row of the screener/movers tables (shared by both). */
export interface PsxScreenRow {
  ticker: string;
  sector: string;
  price: number;
  changePct: number;
  signal: Signal | null;
  rsi: number | null;
  volume: string;
  marketCap: string;
}

/** One index card in the overview grid. */
export interface DisplayIndex {
  key: string;
  code: string;
  name: string;
  value: number;
  change: number;
  changePct: number;
  spark: number[];
  date?: string | null;
}

/** Matches the `days` upper bound on GET /api/quote/{symbol}/history. */
export const MAX_HISTORY_DAYS = 3650;

/** Trading days to request/render per timeframe. */
export function tfDays(tf: string) {
  // "All" was 250 — identical to "1Y" — so the deepest chart the UI could ever
  // draw was one year, even though psx_ohlcv holds ~10 years (back to 2016).
  // 3650 calendar days is the backend's MAX_HISTORY_DAYS bound; at ~250 trading
  // days/year it resolves to roughly 2500 real bars.
  return (
    { "1D": 5, "1W": 14, "1M": 30, "3M": 90, "6M": 130, "1Y": 250, All: MAX_HISTORY_DAYS }[tf] ??
    250
  );
}

export function symbolMeta(sym: string) {
  if (sym === "KSE-100") return { seed: 1, start: 65000, end: 78542.1, vMin: 200, vMax: 800 };
  if (sym === "KSE-100 PR") return { seed: 5, start: 45000, end: 53604.12, vMin: 200, vMax: 800 };
  if (sym === "KSE-30") return { seed: 2, start: 40000, end: 52497.68, vMin: 80, vMax: 300 };
  if (sym === "KMI-30") return { seed: 3, start: 210000, end: 247323.37, vMin: 100, vMax: 350 };
  if (sym === "KMI All Share")
    return { seed: 6, start: 55000, end: 68315.25, vMin: 150, vMax: 700 };
  if (sym === "KSE All Share")
    return { seed: 4, start: 85000, end: 106568.28, vMin: 200, vMax: 900 };
  const s = STOCKS[sym];
  if (!s) return { seed: 9, start: 20000, end: 24000, vMin: 100, vMax: 500 };
  return { seed: s.seed, start: s.start, end: s.price, vMin: 100, vMax: 600 };
}
