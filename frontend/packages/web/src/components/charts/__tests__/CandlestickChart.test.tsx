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

  it("labels an All window with years only", () => {
    const { container } = render(
      <CandlestickChart data={dailyBars(400)} height={400} tf="All" mas={[]} />,
    );
    const ticks = xAxisTicks(container);
    expect(ticks.length).toBeGreaterThan(0);
    expect(ticks.every((v) => /^\d{4}$/.test(v))).toBe(true);
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

  it("renders the intraday series without a timeframe prop defaulting to dates", () => {
    // `tf` defaults to 6M; passing 1D must actually change the axis scale.
    const { container: withTf } = render(
      <CandlestickChart data={intradaySession()} height={400} tf="1D" mas={[]} />,
    );
    const { container: withoutTf } = render(
      <CandlestickChart data={intradaySession()} height={400} mas={[]} />,
    );
    expect(xAxisTicks(withTf)).not.toEqual(xAxisTicks(withoutTf));
  });
});
