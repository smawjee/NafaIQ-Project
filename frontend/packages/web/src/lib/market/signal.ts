import { STOCKS, type Signal } from "@/lib/data";

/**
 * Derive a BUY/SELL signal for a holding.
 *
 * Prefers the known signal from the static PSX metadata (`STOCKS`); otherwise
 * falls back to a gain%-based ladder off the average cost. A non-positive
 * `avgCost` (unknown basis) yields "HOLD".
 *
 * Canonical implementation — previously duplicated in the dashboard and
 * portfolio routes.
 */
export function computeSignal(ticker: string, current: number, avgCost: number): Signal {
  const stock = STOCKS[ticker.toUpperCase()];
  if (stock) return stock.signal;
  if (!avgCost || avgCost <= 0) return "HOLD";
  const gainPct = ((current - avgCost) / avgCost) * 100;
  if (gainPct >= 15) return "STRONG BUY";
  if (gainPct >= 5) return "BUY";
  if (gainPct >= -5) return "HOLD";
  if (gainPct >= -15) return "SELL";
  return "STRONG SELL";
}
