import { createSelector } from "@reduxjs/toolkit";
import { STOCKS } from "@/lib/data";
import type { RootState } from "../index";

// Demo cash-on-hand: keeps the showcase net worth at its familiar PKR 4.28M
// starting point (858,054 initial market value + this balance) while letting
// demo trades move the number.
export const DEMO_CASH_BALANCE = 3_422_446;

export const selectHoldings = (state: RootState) => state.portfolio.holdings;

export const selectHoldingsCount = createSelector(selectHoldings, (holdings) => holdings.length);

export const selectTotalInvested = createSelector(selectHoldings, (holdings) =>
  holdings.reduce((sum, h) => sum + h.avgCost * h.shares, 0),
);

export const selectMarketValue = createSelector(selectHoldings, (holdings) =>
  holdings.reduce((sum, h) => sum + h.current * h.shares, 0),
);

export const selectUnrealizedPnl = createSelector(
  selectMarketValue,
  selectTotalInvested,
  (value, cost) => value - cost,
);

export const selectUnrealizedPnlPct = createSelector(
  selectUnrealizedPnl,
  selectTotalInvested,
  (pnl, cost) => (cost > 0 ? (pnl / cost) * 100 : 0),
);

export const selectSectorAllocation = createSelector(selectHoldings, (holdings) => {
  const map = new Map<string, number>();
  for (const h of holdings) {
    map.set(h.sector, (map.get(h.sector) ?? 0) + h.current * h.shares);
  }
  const total = Array.from(map.values()).reduce((a, b) => a + b, 0);
  if (total <= 0) return [];
  const palette = ["#00d4aa", "#3b82f6", "#f59e0b", "#8b5cf6", "#6b7280", "#ec4899", "#10b981"];
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([name, value], i) => ({
      name,
      value: Math.round((value / total) * 100),
      color: palette[i % palette.length],
    }));
});

// Approximates today's P/L from the fixture change percentages: previous
// close is backed out of the current price for tickers we know about.
export const selectTodayPnl = createSelector(selectHoldings, (holdings) =>
  holdings.reduce((sum, h) => {
    const changePct = STOCKS[h.ticker]?.changePct;
    if (!changePct) return sum;
    const prevClose = h.current / (1 + changePct / 100);
    return sum + (h.current - prevClose) * h.shares;
  }, 0),
);

export const selectTodayPnlPct = createSelector(
  selectTodayPnl,
  selectMarketValue,
  (pnl, marketValue) => {
    const prevValue = marketValue - pnl;
    return prevValue > 0 ? (pnl / prevValue) * 100 : 0;
  },
);

export const selectDemoNetWorth = createSelector(
  selectMarketValue,
  (marketValue) => marketValue + DEMO_CASH_BALANCE,
);

export const selectStockAllocation = createSelector(selectHoldings, (holdings) => {
  const total = holdings.reduce((a, h) => a + h.current * h.shares, 0);
  if (total <= 0) return [];
  const palette = ["#00d4aa", "#3b82f6", "#f59e0b", "#8b5cf6", "#6b7280", "#ec4899", "#10b981"];
  return holdings.map((h, i) => ({
    name: h.ticker,
    value: Math.round(((h.current * h.shares) / total) * 100),
    color: palette[i % palette.length],
  }));
});
