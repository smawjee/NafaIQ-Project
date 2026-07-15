import { STOCKS } from "@/lib/data";

/** Matches the `days` upper bound on GET /api/quote/{symbol}/history. */
export const MAX_HISTORY_DAYS = 3650;

/** Trading days to request/render per timeframe. */
export function tfDays(tf: string) {
  // "All" was 250 — identical to "1Y" — so the deepest chart the UI could ever
  // draw was one year, even though psx_ohlcv holds ~10 years (back to 2016).
  // 3650 calendar days is the backend's MAX_HISTORY_DAYS bound; at ~250 trading
  // days/year it resolves to roughly 2500 real bars.
  return { "1D": 5, "1W": 14, "1M": 30, "3M": 90, "6M": 130, "1Y": 250, All: MAX_HISTORY_DAYS }[tf] ?? 250;
}

export function symbolMeta(sym: string) {
  if (sym === "KSE-100") return { seed: 1, start: 65000, end: 78542.1, vMin: 200, vMax: 800 };
  const s = STOCKS[sym];
  return { seed: s.seed, start: s.start, end: s.price, vMin: 100, vMax: 600 };
}
