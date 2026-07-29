// Frontend mirror of backend app.services.calculations (portfolio).
// Pure functions; no I/O.

export function holdingValue(shares: number | null | undefined, latest: number | null | undefined): number {
  if (shares == null || latest == null) return 0;
  return shares * latest;
}

export function costBasis(shares: number | null | undefined, avgCost: number | null | undefined): number {
  if (shares == null || avgCost == null) return 0;
  return shares * avgCost;
}

export function unrealizedPnl(current: number, cost: number): number {
  return Math.round((current - cost) * 100) / 100;
}

export function pnlPct(unrealized: number, cost: number): number {
  if (cost <= 0) return 0;
  return Math.round((unrealized / cost) * 10000) / 100;
}

export function todayPnl(shares: number, latest: number, previousClose: number): number {
  if (shares == null || latest == null || previousClose == null) return 0;
  return Math.round(shares * (latest - previousClose) * 100) / 100;
}

export function todayPnlPct(today: number, prevValue: number): number {
  if (prevValue <= 0) return 0;
  return Math.round((today / prevValue) * 10000) / 100;
}
