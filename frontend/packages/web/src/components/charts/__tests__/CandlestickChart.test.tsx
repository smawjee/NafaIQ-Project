import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import type { Candle } from "@/lib/data";

/**
 * Regression cover for the chart in the reported screenshot (TSBL @ PKR 2.38):
 * the price axis rendered "3, 2, 2, 2" because precision was hard-coded to zero
 * decimals, and every timeframe drew daily candles on a date-stamped axis.
 *
 * These assert WIRING — that the axis and readout are driven by the timeframe.
 * The formatting rules themselves are pinned exactly in chart-format.test.ts,
 * because jsdom has no layout engine: recharts collapses to a single x tick,
 * emits no y ticks at all, and splits label text across <tspan>s (so "6 Aug"
 * reads back as "6Aug"). Asserting on rendered tick text alone would be
 * testing jsdom's limitations rather than the chart.
 */

function candle(t: number, close: number, spread = 0.06): Candle {
  return {
    date: new Date(t).toISOString(),
    t,
    open: close - spread / 2,
    high: close + spread,
    low: close - spread,
    close,
    volume: 1_200_000,
  };
}

/** A day of 5-minute bars starting at the 09:30 PKT open. */
function intradaySession(): Candle[] {
  const open = Date.UTC(2026, 7, 6, 4, 30); // 09:30 PKT
  return Array.from({ length: 24 }, (_, i) => candle(open + i * 300_000, 2.38 + i * 0.004));
}

function dailyBars(count: number): Candle[] {
  const end = Date.UTC(2026, 7, 6);
  return Array.from({ length: count }, (_, i) =>
    candle(end - (count - 1 - i) * 86_400_000, 2.38 + i * 0.002),
  );
}

/** Tick labels, with the <tspan> split collapsed back out. */
function xAxisTicks(container: HTMLElement): string[] {
  const axis = container.querySelector(".recharts-xAxis");
  return Array.from(axis?.querySelectorAll("text") ?? [])
    .map((n) => (n.textContent ?? "").replace(/\s+/g, ""))
    .filter(Boolean);
}

describe("CandlestickChart time axis", () => {
  it("labels intraday bars with a clock time on the market's timezone", () => {
    const { container } = render(
      <CandlestickChart data={intradaySession()} height={400} tf="1D" mas={[]} />,
    );
    const ticks = xAxisTicks(container);
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.every((v) => /^\d{2}:\d{2}$/.test(v))).toBe(true);
    // Last bar is 09:30 PKT + 23 * 5min = 11:25 PKT. A runner in UTC would
    // read 06:25 if the chart used local time instead of Asia/Karachi.
    expect(ticks).toContain("11:25");
  });

  it("labels a 3M window with day + month", () => {
    const { container } = render(
      <CandlestickChart data={dailyBars(65)} height={400} tf="3M" mas={[]} />,
    );
    const ticks = xAxisTicks(container);
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.every((v) => /^\d{1,2}[A-Z][a-z]{2}$/.test(v))).toBe(true);
  });

  it("labels a multi-year All window with years only", () => {
    // Weekly steps over ~8 years — the real "All" shape (psx_ohlcv reaches
    // back to 2016) without rendering 2,900 bars in jsdom.
    const end = Date.UTC(2026, 7, 6);
    const bars = Array.from({ length: 416 }, (_, i) =>
      candle(end - (415 - i) * 7 * 86_400_000, 2.38 + i * 0.01),
    );
    const { container } = render(<CandlestickChart data={bars} height={400} tf="All" mas={[]} />);
    const ticks = xAxisTicks(container);
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.every((v) => /^\d{4}$/.test(v))).toBe(true);
  });

  it("never repeats an axis label, whatever the window", () => {
    // A 400-day window cannot be labelled by year without repeating, so the
    // formatter steps to the next finer granularity. This is what stopped a 6M
    // chart rendering "Mar 26, Mar 26, Apr 26, Apr 26".
    for (const [tf, bars] of [
      ["All", dailyBars(400)],
      ["1Y", dailyBars(250)],
      ["6M", dailyBars(130)],
      ["3M", dailyBars(65)],
      ["1M", dailyBars(22)],
    ] as const) {
      const { container, unmount } = render(
        <CandlestickChart data={bars} height={400} tf={tf} mas={[]} />,
      );
      const ticks = xAxisTicks(container);
      expect(new Set(ticks).size, `${tf}: ${ticks.join(", ")}`).toBe(ticks.length);
      unmount();
    }
  });
});

describe("CandlestickChart readout", () => {
  it("shows the latest bar's OHLC without hovering", () => {
    render(<CandlestickChart data={dailyBars(30)} height={400} tf="1M" mas={[]} />);
    // The old floating tooltip only appeared on hover, and then sat on top of
    // the candles it described.
    for (const label of ["O", "H", "L", "C", "V"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("keeps a low-priced stock's figures at usable precision", () => {
    // The reported bug: a 2.32-2.50 range rendered as whole numbers, so every
    // price on screen read "2".
    render(<CandlestickChart data={dailyBars(30)} height={400} tf="1M" mas={[]} />);
    // Last close is 2.38 + 29 * 0.002.
    expect(screen.getByText("2.438")).toBeInTheDocument();
  });

  it("names the timezone on an intraday bar", () => {
    render(<CandlestickChart data={intradaySession()} height={400} tf="1D" mas={[]} />);
    expect(screen.getByText(/11:25 PKT/)).toBeInTheDocument();
  });

  it("renders volume compactly instead of gluing an M onto a raw count", () => {
    // The old tooltip printed `{p.volume}M`, so 1,200,000 rendered "1200000M".
    render(<CandlestickChart data={dailyBars(5)} height={400} tf="1M" mas={[]} />);
    expect(screen.getByText("1.2M")).toBeInTheDocument();
  });
});

describe("CandlestickChart edge cases", () => {
  it("says there is no data rather than drawing an empty axis", () => {
    render(<CandlestickChart data={[]} height={400} tf="1M" />);
    expect(screen.getByText("No price data for this range")).toBeInTheDocument();
  });

  it("survives a single flat bar without a NaN domain", () => {
    // Zero price span AND zero volume: the pad and the volume domain both
    // divided by a range of 0 before the guards were added.
    const flat: Candle[] = [
      {
        date: "2026-08-06",
        t: Date.UTC(2026, 7, 6),
        open: 2,
        high: 2,
        low: 2,
        close: 2,
        volume: 0,
      },
    ];
    const { container } = render(<CandlestickChart data={flat} height={400} tf="1M" mas={[]} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.textContent).not.toContain("NaN");
  });

  it("labels intraday bars by the clock even when tf says otherwise", () => {
    // The scale is derived from the DATA, not the timeframe label — that is
    // what stops a daily-bar fallback being labelled with clock times. The
    // converse must hold too: intraday bars stay clock-labelled even under the
    // default tf ("6M"), so the axis can never contradict what is drawn.
    const { container: withTf } = render(
      <CandlestickChart data={intradaySession()} height={400} tf="1D" mas={[]} />,
    );
    const { container: withoutTf } = render(
      <CandlestickChart data={intradaySession()} height={400} mas={[]} />,
    );
    expect(xAxisTicks(withTf).every((t) => /^\d{2}:\d{2}$/.test(t))).toBe(true);
    expect(xAxisTicks(withoutTf)).toEqual(xAxisTicks(withTf));
  });
});

describe("CandlestickChart 1D/1W fallback to daily candles", () => {
  /** Exactly what the PSX page draws when psx_intraday is still empty. */
  function dailyFallback(count: number): Candle[] {
    const end = Date.parse("2026-08-06");
    return Array.from({ length: count }, (_, i) => {
      const t = end - (count - 1 - i) * 86_400_000;
      return {
        date: new Date(t).toISOString().slice(0, 10),
        t,
        open: 25 + i * 0.1,
        high: 26 + i * 0.1,
        low: 24 + i * 0.1,
        close: 25.5 + i * 0.1,
        volume: 1_800_000,
      };
    });
  }

  it("does not render every tick as 05:00 on 1W", () => {
    // The reported bug. A daily bar is UTC midnight, which is 05:00 in
    // Karachi, so the intraday formatter collapsed the whole axis to one
    // repeated clock time.
    const { container } = render(
      <CandlestickChart data={dailyFallback(20)} height={400} tf="1W" mas={[]} />,
    );
    const ticks = xAxisTicks(container);
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks).not.toContain("05:00");
    expect(ticks.every((t) => !t.includes(":"))).toBe(true);
    expect(ticks.every((t) => /^\d{1,2}[A-Z][a-z]{2}$/.test(t))).toBe(true);
  });

  it("does not render every tick as 05:00 on 1D", () => {
    const { container } = render(
      <CandlestickChart data={dailyFallback(10)} height={400} tf="1D" mas={[]} />,
    );
    const ticks = xAxisTicks(container);
    expect(ticks.every((t) => !t.includes(":"))).toBe(true);
  });

  it("the readout shows a date, not a 05:00 PKT clock time", () => {
    render(<CandlestickChart data={dailyFallback(20)} height={400} tf="1W" mas={[]} />);
    expect(screen.queryByText(/PKT/)).toBeNull();
    expect(screen.queryByText(/05:00/)).toBeNull();
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("still uses clock time when real intraday bars arrive on 1W", () => {
    const open = Date.UTC(2026, 7, 6, 4, 30);
    const bars: Candle[] = Array.from({ length: 40 }, (_, i) => {
      const t = open + i * 300_000;
      return {
        date: new Date(t).toISOString(),
        t,
        open: 25,
        high: 26,
        low: 24,
        close: 25.5,
        volume: 1000,
      };
    });
    const { container } = render(<CandlestickChart data={bars} height={400} tf="1W" mas={[]} />);
    expect(xAxisTicks(container).every((t) => /^\d{2}:\d{2}$/.test(t))).toBe(true);
  });
});
