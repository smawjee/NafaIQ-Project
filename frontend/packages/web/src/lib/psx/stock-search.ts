import type { ApiSymbolInfo, ApiMarketSnapshotItem } from "@/lib/psx/types";

/**
 * A single stock search result: identity + (optional) live price.
 * Shared by the Watchlist "Add Stock" dropdown and the global search bar.
 */
export interface StockSearchResult {
  symbol: string;
  name: string;
  sector: string | null;
  price: number | null;
  change: number | null;
  changePct: number | null;
  logoUrl: string | null;
}

/** TradingView-hosted company logo (SVG) from a logoid, or null. */
export function logoUrlFor(logoid: string | null | undefined): string | null {
  return logoid ? `https://s3-symbol-logo.tradingview.com/${logoid}.svg` : null;
}

/**
 * Build the full searchable universe by joining the PSX symbol list
 * (`/api/symbols`) with the batched market snapshot (`/api/market/snapshot`).
 * Prices come from a single snapshot call — never one request per stock.
 */
export function buildStockUniverse(
  symbols: ApiSymbolInfo[] | undefined,
  snapshot: ApiMarketSnapshotItem[] | undefined,
): StockSearchResult[] {
  if (!symbols) return [];
  const priceMap = new Map((snapshot ?? []).map((s) => [s.symbol, s]));
  return symbols.map((s) => {
    const p = priceMap.get(s.symbol);
    return {
      symbol: s.symbol,
      name: s.name,
      sector: s.sector,
      price: p?.price ?? null,
      change: p?.change ?? null,
      changePct: p?.change_pct ?? null,
      logoUrl: logoUrlFor(s.logoid),
    };
  });
}

/**
 * Case-insensitive, partial match over ticker AND company name, ranked:
 * exact ticker > ticker prefix > ticker contains > name prefix > name contains.
 * With an empty query, returns the first `limit` (universe browse).
 */
export function matchStocks(
  universe: StockSearchResult[],
  query: string,
  limit = 50,
): StockSearchResult[] {
  const q = query.trim().toUpperCase();
  if (!q) return universe.slice(0, limit);

  const scored: { r: StockSearchResult; score: number }[] = [];
  for (const r of universe) {
    const sym = r.symbol.toUpperCase();
    const name = r.name.toUpperCase();
    let score = -1;
    if (sym === q) score = 100;
    else if (sym.startsWith(q)) score = 80;
    else if (sym.includes(q)) score = 60;
    else if (name.startsWith(q)) score = 50;
    else if (name.includes(q)) score = 30;
    if (score >= 0) scored.push({ r, score });
  }
  scored.sort((a, b) => b.score - a.score || a.r.symbol.localeCompare(b.r.symbol));
  return scored.slice(0, limit).map((x) => x.r);
}
