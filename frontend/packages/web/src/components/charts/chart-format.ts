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
