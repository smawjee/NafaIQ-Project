/**
 * Timeframe-aware formatting for the price charts.
 *
 * Kept separate from the chart components (and free of React) so the rules that
 * actually decide what a reader sees — tick granularity, price precision,
 * volume units — are unit-testable rather than buried in JSX.
 */

/** PSX trades on Pakistan time. A trader in London must read the market's
 * clock, not their own, so every intraday timestamp is rendered in PKT. */
const MARKET_TZ = "Asia/Karachi";

/** Dates render in en-GB regardless of UI language: the axis is dense, and a
 * fixed, short Latin form stays legible next to the mono price ticks. */
const DATE_LOCALE = "en-GB";

export type ChartScale = "intraday" | "day" | "month" | "year";

const SCALE_BY_TF: Record<string, ChartScale> = {
  "1D": "intraday",
  "1W": "intraday",
  "1M": "day",
  "3M": "day",
  "6M": "month",
  "1Y": "month",
  All: "year",
};

export function scaleFor(tf: string): ChartScale {
  return SCALE_BY_TF[tf] ?? "day";
}

const DAY_MS = 24 * 60 * 60 * 1000;
/** A daily-bar window wider than this reads better labelled by month. */
const LONG_WINDOW_MS = 400 * DAY_MS;

/**
 * The scale to actually draw with, decided by the DATA rather than the label.
 *
 * 1D and 1W ask for intraday bars but fall back to daily ones whenever
 * `psx_intraday` has nothing yet — a fresh deployment, a symbol that has not
 * traded, or any index (the snapshot carries no index rows). The timeframe
 * still said "intraday", so daily bars were formatted with the clock formatter:
 * a daily bar's timestamp is UTC midnight, which in Asia/Karachi is 05:00, so
 * EVERY tick on the axis rendered "05:00" and the readout claimed
 * "16 Jul 2026 · 05:00 PKT" for a whole session's candle.
 *
 * Deriving the scale from the bar spacing means the axis cannot disagree with
 * what is on screen, whichever series the chart ended up with.
 */
export function resolveScale(tf: string, bars: readonly { t: number }[]): ChartScale {
  const declared = scaleFor(tf);
  if (bars.length === 0) return declared === "intraday" ? "day" : declared;

  // A daily bar is parsed from "YYYY-MM-DD", so its instant is EXACTLY UTC
  // midnight; a 5-minute bar never is. That is an exact discriminator rather
  // than a guess from bar spacing, and it still works when only one bar is on
  // screen.
  const isIntradayData = bars.some((b) => Number.isFinite(b.t) && b.t % DAY_MS !== 0);
  if (isIntradayData) return "intraday";

  // Daily bars. Honour the timeframe's own granularity, except when it asked
  // for intraday — then pick by how much calendar the fallback window covers.
  if (declared !== "intraday") return declared;
  const span = bars[bars.length - 1].t - bars[0].t;
  return span > LONG_WINDOW_MS ? "month" : "day";
}

const formatters = new Map<string, Intl.DateTimeFormat>();

function df(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = JSON.stringify(options);
  let f = formatters.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(DATE_LOCALE, { timeZone: MARKET_TZ, ...options });
    formatters.set(key, f);
  }
  return f;
}

/**
 * Axis tick label. Deliberately terse — the tooltip carries the full instant,
 * so the axis only needs enough to orient within the visible window.
 */
export function formatAxisTick(t: number, scale: ChartScale): string {
  if (!Number.isFinite(t)) return "";
  const d = new Date(t);
  switch (scale) {
    case "intraday":
      return df({ hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
    case "day":
      return df({ day: "numeric", month: "short" }).format(d);
    case "month":
      return df({ month: "short", year: "2-digit" }).format(d);
    case "year":
      return df({ year: "numeric" }).format(d);
  }
}

/** Tooltip heading — always unambiguous, including the year. */
export function formatTooltipLabel(t: number, scale: ChartScale): string {
  if (!Number.isFinite(t)) return "";
  const d = new Date(t);
  if (scale === "intraday") {
    const day = df({ day: "numeric", month: "short", year: "numeric" }).format(d);
    const time = df({ hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
    return `${day} · ${time} PKT`;
  }
  return df({ weekday: "short", day: "numeric", month: "short", year: "numeric" }).format(d);
}

/** Next finer granularity, for resolving duplicate axis labels. */
const FINER: Record<ChartScale, ChartScale | null> = {
  year: "month",
  month: "day",
  day: "intraday",
  intraday: null,
};

/**
 * Evenly spaced tick values across the visible bars, endpoints included.
 *
 * Choosing the ticks ourselves (rather than leaving it to `minTickGap`) is what
 * makes `scaleForTicks` possible: the label format can only be validated once
 * it is known which instants will actually be labelled.
 */
export function pickTickValues(bars: readonly { t: number }[], maxTicks = 7): number[] {
  if (bars.length === 0) return [];
  if (bars.length <= maxTicks) return bars.map((b) => b.t);
  const step = (bars.length - 1) / (maxTicks - 1);
  const out: number[] = [];
  for (let i = 0; i < maxTicks; i++) out.push(bars[Math.round(i * step)].t);
  return Array.from(new Set(out));
}

/**
 * The coarsest granularity that still labels every tick distinctly.
 *
 * A 6-month window puts roughly two ticks inside each month, so a "MMM yy"
 * label rendered the axis as "Feb 26, Mar 26, Mar 26, Apr 26, Apr 26, …" —
 * adjacent ticks carrying the same text, which tells the reader nothing about
 * where they are and looks like a rendering fault. Stepping to the next finer
 * format until the labels are unique fixes it for every window rather than
 * hand-tuning a threshold per timeframe.
 */
export function scaleForTicks(scale: ChartScale, tickValues: readonly number[]): ChartScale {
  let current: ChartScale | null = scale;
  while (current) {
    const labels = tickValues.map((t) => formatAxisTick(t, current as ChartScale));
    if (new Set(labels).size === labels.length) return current;
    const next: ChartScale | null = FINER[current];
    if (!next) return current;
    current = next;
  }
  return scale;
}

/**
 * Decimal places for the price axis, chosen from the visible range.
 *
 * The chart previously hard-coded `fmtNum(v, 0)`. On a PKR 2.38 stock whose
 * window spans 2.37–2.53 that rounded every single tick to "2" — four axis
 * labels reading 3, 2, 2, 2, which is what the reported screenshot shows.
 * Precision has to follow the span, not the convention for index values.
 */
export function priceDecimals(span: number): number {
  if (!Number.isFinite(span) || span <= 0) return 2;
  if (span >= 500) return 0;
  if (span >= 50) return 1;
  if (span >= 1) return 2;
  if (span >= 0.1) return 3;
  return 4;
}

/**
 * Bar width below which a candle body stops carrying information.
 *
 * Under ~3px the body and wick collapse into the same smear, so the chart
 * draws a single 1px line per bar instead — dense but honest. Above it, the
 * body is inset to leave a visible gap between neighbours.
 */
export const MIN_CANDLE_BODY_PX = 3;
