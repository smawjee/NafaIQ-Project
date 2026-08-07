import { describe, expect, it } from "vitest";
import type { Candle } from "@/lib/data";
import {
  DAILY_FETCH_DAYS,
  FULL_FETCH_DAYS,
  fetchDaysFor,
  indexBarsHaveNoRange,
  tfSpec,
  windowBars,
  windowStartIndex,
} from "@/features/psx/psx.utils";

/**
 * The bug these pin: `tfDays()` returned ONE number that was used both as a
 * calendar-day count for the API request and as a BAR count for the render
 * slice. PSX trades ~250 sessions per 365 calendar days, so every window
 * over-rendered by ~1.45x — and "1D" resolved to `slice(-5)`, i.e. a full
 * trading week of daily candles.
 */

/** Daily bars, one per weekday, ending on `end`. */
function dailyBars(end: string, count: number): Candle[] {
  const out: Candle[] = [];
  const cursor = new Date(`${end}T00:00:00Z`);
  while (out.length < count) {
    const day = cursor.getUTCDay();
    if (day !== 0 && day !== 6) {
      const iso = cursor.toISOString().slice(0, 10);
      out.push({ date: iso, t: cursor.getTime(), open: 1, high: 1, low: 1, close: 1, volume: 1 });
    }
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return out.reverse();
}

describe("tfSpec", () => {
  it("routes 1D and 1W to the intraday series", () => {
    expect(tfSpec("1D").kind).toBe("intraday");
    expect(tfSpec("1W").kind).toBe("intraday");
    expect(tfSpec("1D").sessions).toBe(1);
    expect(tfSpec("1W").sessions).toBe(5);
  });

  it("routes every longer timeframe to daily bars", () => {
    for (const tf of ["1M", "3M", "6M", "1Y", "All"]) {
      expect(tfSpec(tf).kind).toBe("daily");
    }
  });

  it("falls back to the 6M window for an unknown timeframe", () => {
    expect(tfSpec("bogus")).toEqual(tfSpec("6M"));
  });
});

describe("fetchDaysFor", () => {
  it("uses one shared depth for every bounded timeframe", () => {
    // One depth means switching 1M -> 3M -> 6M -> 1Y re-slices cached bars
    // instead of firing a new request per button.
    const depths = ["1D", "1W", "1M", "3M", "6M", "1Y"].map(fetchDaysFor);
    expect(new Set(depths).size).toBe(1);
    expect(depths[0]).toBe(DAILY_FETCH_DAYS);
  });

  it("covers a 1Y window plus the MA200 warmup", () => {
    // 365 calendar days of window + ~200 trading days (~290 calendar) of
    // warmup, or MA200 is null across the whole visible 1Y range.
    expect(DAILY_FETCH_DAYS).toBeGreaterThanOrEqual(365 + 290);
  });

  it("only 'All' pays for the full history", () => {
    expect(fetchDaysFor("All")).toBe(FULL_FETCH_DAYS);
    expect(FULL_FETCH_DAYS).toBe(3650);
  });
});

describe("windowStartIndex", () => {
  const bars = dailyBars("2026-08-06", 400);

  it("measures the window from the newest bar, not from today", () => {
    // A dataset that ends on a Friday, viewed on the following Monday, must
    // still show a full month — not a month minus the weekend.
    const start = windowStartIndex(bars, "1M");
    const first = bars[start];
    expect(first.date >= "2026-07-06").toBe(true);
    expect(bars[start - 1].date < "2026-07-06").toBe(true);
  });

  it("gives 3M about three calendar months, not 90 trading days", () => {
    // The old code sliced 90 BARS, which is ~4.3 calendar months.
    const visible = windowBars(bars, "3M");
    expect(visible[0].date >= "2026-05-06").toBe(true);
    // ~21.7 trading days per month => ~65 bars, never the old 90.
    expect(visible.length).toBeLessThan(75);
    expect(visible.length).toBeGreaterThan(55);
  });

  it("gives 1M about a month of sessions", () => {
    const visible = windowBars(bars, "1M");
    expect(visible.length).toBeLessThan(26);
    expect(visible.length).toBeGreaterThan(17);
  });

  it("returns the whole series for All", () => {
    expect(windowStartIndex(bars, "All")).toBe(0);
    expect(windowBars(bars, "All")).toHaveLength(bars.length);
  });

  it("returns the whole series when history is shorter than the window", () => {
    const short = dailyBars("2026-08-06", 5);
    expect(windowStartIndex(short, "1Y")).toBe(0);
  });

  it("handles an empty series without throwing", () => {
    expect(windowStartIndex([], "3M")).toBe(0);
    expect(windowBars([], "3M")).toEqual([]);
  });

  it("never returns an empty window for a non-empty series", () => {
    // A single bar older than the window must still be drawn — an empty chart
    // reads as "broken", not as "no recent trades".
    const stale = dailyBars("2020-01-10", 3);
    expect(windowBars(stale, "1M").length).toBeGreaterThan(0);
  });

  it("windows intraday timeframes by session count", () => {
    const now = Date.UTC(2026, 7, 6, 9, 0);
    const intraday: Candle[] = [];
    for (let session = 0; session < 3; session++) {
      for (let bar = 0; bar < 4; bar++) {
        const t = now - session * 86_400_000 + bar * 300_000;
        intraday.push({
          date: new Date(t).toISOString(),
          t,
          open: 1,
          high: 1,
          low: 1,
          close: 1,
          volume: 1,
        });
      }
    }
    intraday.sort((a, b) => a.t - b.t);
    // 1D keeps only the newest session's bars.
    expect(windowBars(intraday, "1D")).toHaveLength(4);
    // 1W spans five sessions, so three sessions of data all survive.
    expect(windowBars(intraday, "1W")).toHaveLength(12);
  });
});

describe("indexBarsHaveNoRange", () => {
  it("detects the coalesced shape the API actually returns", () => {
    // Every KSE-100 bar arrives as open == high == low == close, because the
    // API fills the missing columns from the close. The old null-only check
    // never fired and the chart drew 1,000 zero-range dojis.
    const bars = Array.from({ length: 5 }, (_, i) => ({
      open: 180000 + i,
      high: 180000 + i,
      low: 180000 + i,
      close: 180000 + i,
    }));
    expect(indexBarsHaveNoRange(bars)).toBe(true);
  });

  it("detects the all-null shape too", () => {
    const bars = [{ open: null, high: null, low: null, close: 180000 }];
    expect(indexBarsHaveNoRange(bars)).toBe(true);
  });

  it("keeps candles when the bars carry a real range", () => {
    const bars = [
      { open: 100, high: 110, low: 95, close: 105 },
      { open: 105, high: 112, low: 101, close: 108 },
    ];
    expect(indexBarsHaveNoRange(bars)).toBe(false);
  });

  it("keeps candles when even one bar has a range", () => {
    const bars = [
      { open: 100, high: 100, low: 100, close: 100 },
      { open: 100, high: 110, low: 95, close: 105 },
    ];
    expect(indexBarsHaveNoRange(bars)).toBe(false);
  });

  it("is false for an empty series so an empty chart is not forced to a line", () => {
    expect(indexBarsHaveNoRange([])).toBe(false);
  });
});
