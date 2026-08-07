import { STOCKS, type Candle, type Signal } from "@/lib/data";
import type { ApiSignalBreakdown } from "@/lib/psx/types";

/** One row of the screener/movers tables (shared by both). */
export interface PsxScreenRow {
  ticker: string;
  sector: string;
  price: number;
  changePct: number;
  signal: Signal | null;
  signalDetails?: ApiSignalBreakdown | null;
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

/**
 * Which series a timeframe reads from, and how much of it to show.
 *
 * This replaces `tfDays()`, which returned a single number that callers used
 * for two incompatible things: as a CALENDAR-day count for the API request and
 * as a BAR count for the render slice. PSX trades ~250 sessions per 365
 * calendar days, so every window over-rendered by ~1.45x ("3M" drew 90 bars =
 * ~4.3 months), and "1D" collapsed to `slice(-5)` — one full trading week of
 * daily candles rather than a single day.
 */
export type TimeframeKind = "intraday" | "daily";

export interface TimeframeSpec {
  kind: TimeframeKind;
  /** Trading sessions to show. Intraday only. */
  sessions: number;
  /** Calendar months to show, measured back from the newest bar. Daily only. */
  months: number;
}

const TF_SPECS: Record<string, TimeframeSpec> = {
  // 1D and 1W read `psx_intraday` (5-minute bars). Daily bars cannot express
  // either window: one trading day is a single daily candle.
  "1D": { kind: "intraday", sessions: 1, months: 0 },
  "1W": { kind: "intraday", sessions: 5, months: 0 },
  "1M": { kind: "daily", sessions: 0, months: 1 },
  "3M": { kind: "daily", sessions: 0, months: 3 },
  "6M": { kind: "daily", sessions: 0, months: 6 },
  "1Y": { kind: "daily", sessions: 0, months: 12 },
  // 0 months = unbounded; `windowStartIndex` returns 0 and the whole series draws.
  All: { kind: "daily", sessions: 0, months: 0 },
};

export function tfSpec(tf: string): TimeframeSpec {
  return TF_SPECS[tf] ?? TF_SPECS["6M"];
}

/**
 * One fetch depth for every bounded timeframe.
 *
 * 655 days is a 1Y window (365) plus the ~290 calendar days of warmup MA200
 * needs to be non-null at the window's left edge — the MAs are computed over
 * the full series and sliced with it, so a short fetch would blank them.
 * Rounding to 750 gives headroom over holiday-heavy stretches.
 *
 * Sharing one depth across 1D…1Y matters because the depth is part of the
 * React Query key: distinct values per timeframe meant every toolbar click
 * fired a fresh request for bars already in cache.
 */
export const DAILY_FETCH_DAYS = 750;
export const FULL_FETCH_DAYS = MAX_HISTORY_DAYS;

export function fetchDaysFor(tf: string): number {
  return tfSpec(tf).months === 0 && tfSpec(tf).kind === "daily"
    ? FULL_FETCH_DAYS
    : DAILY_FETCH_DAYS;
}

const DAY_MS = 86_400_000;

/**
 * Index of the first bar inside `tf`'s window.
 *
 * The cutoff is measured from the NEWEST BAR, not from `Date.now()`. Measuring
 * from now would shrink every window over a weekend or a holiday, and would
 * empty the chart entirely for a symbol that has stopped trading.
 *
 * Returns 0 rather than an empty window when the whole series predates the
 * cutoff: a chart with nothing in it reads as broken, not as "no recent trades".
 */
export function windowStartIndex(bars: readonly { t: number }[], tf: string): number {
  if (bars.length === 0) return 0;
  const spec = tfSpec(tf);
  const last = bars[bars.length - 1].t;

  let cutoff: number;
  if (spec.kind === "intraday") {
    // Sessions are counted by distinct local calendar days present in the data
    // rather than by subtracting N*24h — PSX is closed at weekends, so five
    // sessions can span nine calendar days.
    const days: number[] = [];
    for (let i = bars.length - 1; i >= 0; i--) {
      const day = Math.floor(bars[i].t / DAY_MS);
      if (days[days.length - 1] !== day) {
        if (days.length === spec.sessions) return i + 1;
        days.push(day);
      }
    }
    return 0;
  } else if (spec.months === 0) {
    return 0;
  } else {
    const d = new Date(last);
    d.setMonth(d.getMonth() - spec.months);
    cutoff = d.getTime();
  }

  const start = bars.findIndex((b) => b.t >= cutoff);
  return start <= 0 ? 0 : start;
}

/** The bars `tf` should draw. */
export function windowBars<T extends { t: number }>(bars: readonly T[], tf: string): T[] {
  return bars.slice(windowStartIndex(bars, tf));
}

/**
 * True when index bars carry no intraday range, so a candlestick has nothing
 * to draw and the chart should show a line instead.
 *
 * Two shapes reach this. DPS omits open/high/low on some index rows, and the
 * API coalesces those missing columns to the close — so bars arrive either with
 * nulls or, far more often, as open == high == low == close. Testing only for
 * null (as this once did) missed the second shape entirely, and the KSE-100
 * chart rendered 1,000 zero-range dojis: a row of 1px dashes where a curve
 * belonged. Any bar with a high above its low still means real candles.
 */
export function indexBarsHaveNoRange(
  bars: readonly {
    open?: number | null;
    high?: number | null;
    low?: number | null;
    close: number;
  }[],
): boolean {
  if (bars.length === 0) return false;
  return bars.every((b) => {
    if (b.open == null && b.high == null && b.low == null) return true;
    return (b.high ?? b.close) === (b.low ?? b.close);
  });
}

/**
 * Daily bars to draw when an intraday timeframe has no intraday data.
 *
 * `psx_intraday` only accumulates while the market is open and is pruned to a
 * short window, so 1D/1W have nothing to show on a fresh deployment, outside
 * trading hours on a symbol that never traded, or for a newly-listed ticker.
 * Windowing the DAILY series by the intraday rule would be literally correct
 * and useless — "1D" would resolve to a single candle. These counts give a
 * legible fallback instead, and the UI says which series it is showing.
 */
export function intradayFallbackBars(tf: string): number {
  return { "1D": 10, "1W": 20 }[tf] ?? 20;
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
