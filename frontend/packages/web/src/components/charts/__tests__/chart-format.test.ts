import { describe, expect, it } from "vitest";
import {
  formatAxisTick,
  formatTooltipLabel,
  priceDecimals,
  scaleFor,
} from "@/components/charts/chart-format";

describe("scaleFor", () => {
  it("uses clock time for intraday timeframes and calendar units above them", () => {
    expect(scaleFor("1D")).toBe("intraday");
    expect(scaleFor("1W")).toBe("intraday");
    expect(scaleFor("1M")).toBe("day");
    expect(scaleFor("3M")).toBe("day");
    expect(scaleFor("6M")).toBe("month");
    expect(scaleFor("1Y")).toBe("month");
    expect(scaleFor("All")).toBe("year");
  });

  it("falls back to day granularity for an unknown timeframe", () => {
    expect(scaleFor("bogus")).toBe("day");
  });
});

describe("formatAxisTick", () => {
  // 2026-08-06T04:35:00Z is 09:35 in Karachi — the PSX morning session.
  const openingBell = Date.UTC(2026, 7, 6, 4, 35);

  it("renders intraday ticks on the market clock, not the viewer's", () => {
    // The assertion is the point: a browser in UTC or London must still read
    // 09:35, because that is when the trade happened on the exchange.
    expect(formatAxisTick(openingBell, "intraday")).toBe("09:35");
  });

  it("uses 24-hour time so 09:35 and 21:35 never collide", () => {
    expect(formatAxisTick(Date.UTC(2026, 7, 6, 16, 35), "intraday")).toBe("21:35");
  });

  it("renders day, month and year scales at decreasing precision", () => {
    expect(formatAxisTick(openingBell, "day")).toBe("6 Aug");
    expect(formatAxisTick(openingBell, "month")).toBe("Aug 26");
    expect(formatAxisTick(openingBell, "year")).toBe("2026");
  });

  it("does not shift a daily bar into the previous day", () => {
    // Daily bars parse as UTC midnight; converting to PKT (+5) must stay on
    // the same calendar date or every candle would be labelled a day early.
    expect(formatAxisTick(Date.parse("2026-08-06"), "day")).toBe("6 Aug");
  });

  it("returns an empty string for a non-finite timestamp", () => {
    expect(formatAxisTick(NaN, "day")).toBe("");
  });
});

describe("formatTooltipLabel", () => {
  const openingBell = Date.UTC(2026, 7, 6, 4, 35);

  it("names the timezone on intraday bars", () => {
    expect(formatTooltipLabel(openingBell, "intraday")).toBe("6 Aug 2026 · 09:35 PKT");
  });

  it("always carries the year on daily bars", () => {
    expect(formatTooltipLabel(openingBell, "day")).toContain("2026");
    expect(formatTooltipLabel(openingBell, "day")).toContain("Thu");
  });
});

describe("priceDecimals", () => {
  it("keeps a low-priced stock readable", () => {
    // The reported bug: TSBL spans 2.37-2.53 and every axis tick rendered "2".
    expect(priceDecimals(2.53 - 2.37)).toBe(3);
    expect((2.44).toFixed(priceDecimals(0.16))).toBe("2.440");
  });

  it("drops decimals on index-scale ranges", () => {
    expect(priceDecimals(4000)).toBe(0);
  });

  it("scales through the middle of the range", () => {
    expect(priceDecimals(120)).toBe(1);
    expect(priceDecimals(8)).toBe(2);
    expect(priceDecimals(0.02)).toBe(4);
  });

  it("falls back to 2 for a degenerate span", () => {
    // Every bar at the same price — a suspended stock, or a single bar.
    expect(priceDecimals(0)).toBe(2);
    expect(priceDecimals(NaN)).toBe(2);
  });
});
