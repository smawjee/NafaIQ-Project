import { describe, expect, it } from "vitest";
import { calculateZakatSummary } from "./zakat.logic";

const gold = { pkr_per_tola: 449_400 };
const silver = { pkr_per_tola: 6_000 };

function baseValues(overrides: Record<string, number> = {}) {
  return {
    cash: 0,
    gold: 0,
    silver: 0,
    stocks: 0,
    funds: 0,
    business: 0,
    receivables: 0,
    property: 0,
    loans: 0,
    credit: 0,
    ...overrides,
  };
}

describe("calculateZakatSummary", () => {
  it("values gold and silver from live per-tola rates", () => {
    const summary = calculateZakatSummary({
      values: baseValues({ cash: 100_000 }),
      goldTola: 2.5,
      silverTola: 10,
      gold,
      silver,
      nisabSource: "silver",
    });

    expect(summary.assetValues.gold).toBe(1_123_500);
    expect(summary.assetValues.silver).toBe(60_000);
    expect(summary.totalAssets).toBe(1_283_500);
  });

  it("uses silver nisab by default and calculates 2.5 percent on net zakatable wealth", () => {
    const summary = calculateZakatSummary({
      values: baseValues({ cash: 1_000_000, stocks: 500_000, loans: 200_000, credit: 50_000 }),
      goldTola: 1,
      silverTola: 0,
      gold,
      silver,
      nisabSource: "silver",
    });

    expect(summary.silverNisab).toBe(315_000);
    expect(summary.nisabValue).toBe(315_000);
    expect(summary.totalAssets).toBe(1_949_400);
    expect(summary.totalLiabilities).toBe(250_000);
    expect(summary.zakatableWealth).toBe(1_699_400);
    expect(summary.aboveNisab).toBe(true);
    expect(summary.zakatDue).toBe(42_485);
  });

  it("can calculate against gold nisab", () => {
    const summary = calculateZakatSummary({
      values: baseValues({ cash: 500_000 }),
      goldTola: 0,
      silverTola: 0,
      gold,
      silver,
      nisabSource: "gold",
    });

    expect(summary.goldNisab).toBe(3_370_500);
    expect(summary.nisabValue).toBe(3_370_500);
    expect(summary.aboveNisab).toBe(false);
    expect(summary.zakatDue).toBe(0);
  });

  it("does not calculate when live metals are missing or stale", () => {
    const missing = calculateZakatSummary({
      values: baseValues({ cash: 1_000_000 }),
      goldTola: 0,
      silverTola: 0,
      gold,
      nisabSource: "silver",
    });
    const stale = calculateZakatSummary({
      values: baseValues({ cash: 1_000_000 }),
      goldTola: 0,
      silverTola: 0,
      gold,
      silver,
      stale: true,
      nisabSource: "silver",
    });

    expect(missing.calculationReady).toBe(false);
    expect(missing.nisabValue).toBe(0);
    expect(missing.zakatDue).toBe(0);
    expect(stale.calculationReady).toBe(false);
    expect(stale.nisabValue).toBe(0);
    expect(stale.zakatDue).toBe(0);
  });
});
