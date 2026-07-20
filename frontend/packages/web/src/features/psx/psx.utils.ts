import { STOCKS, type Candle, type Signal } from "@/lib/data";

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

export interface LiveCandleInput {
  price: number | null | undefined;
  change?: number | null;
  changePct?: number | null;
  dayHigh?: number | null;
  dayLow?: number | null;
  volume?: number | null;
  date?: string | null;
}

function localIsoDate() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 10);
}

function previousCloseFromLive(live: LiveCandleInput): number | null {
  const price = live.price;
  if (price == null || !Number.isFinite(price) || price <= 0) return null;
  if (live.change != null && Number.isFinite(live.change)) {
    return price - live.change;
  }
  if (live.changePct != null && Number.isFinite(live.changePct) && live.changePct > -100) {
    return price / (1 + live.changePct / 100);
  }
  return null;
}

/**
 * Historical OHLCV is EOD, while snapshot/index cards are live. Merge the
 * current tick into the latest candle so chart headers, tooltips, watchlists,
 * and index cards all speak from the same price.
 */
export function reconcileLiveCandle(rows: Candle[], live: LiveCandleInput | null | undefined) {
  if (!live) return rows;
  const price = live?.price;
  if (price == null || !Number.isFinite(price) || price <= 0) return rows;

  const date = live?.date?.slice(0, 10) || localIsoDate();
  const prevClose = previousCloseFromLive(live);
  const existingIndex = rows.findIndex((row) => row.date === date);
  const existing = existingIndex >= 0 ? rows[existingIndex] : undefined;
  const prior = existing ?? rows[rows.length - 1];
  const open = existing?.open ?? prevClose ?? prior?.close ?? price;
  const high = Math.max(
    ...[existing?.high, live?.dayHigh, open, price].filter(
      (value): value is number => value != null && Number.isFinite(value),
    ),
  );
  const low = Math.min(
    ...[existing?.low, live?.dayLow, open, price].filter(
      (value): value is number => value != null && Number.isFinite(value),
    ),
  );
  const volume = live?.volume ?? existing?.volume ?? prior?.volume ?? 0;
  const candle: Candle = {
    date,
    t: new Date(date).getTime(),
    open,
    high,
    low,
    close: price,
    volume,
  };

  if (existingIndex >= 0) {
    return rows.map((row, index) => (index === existingIndex ? candle : row));
  }
  return [...rows, candle];
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
