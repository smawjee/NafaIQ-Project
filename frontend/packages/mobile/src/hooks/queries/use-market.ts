// React Query hooks for the PSX market backend. Ported from the web app's
// src/hooks/psx/use-psx.ts (reference implementation) — same query keys and
// staleTime/refetch choices so behavior stays in lockstep across clients.
import { useEffect, useRef } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ApiMarketSnapshotItem,
  ApiSymbolInfo,
  Candle,
} from "@nafaiq/shared";

import {
  fetchAnnouncements,
  fetchBatchSignals,
  fetchCompanyProfile,
  fetchDividends,
  fetchFundamentals,
  fetchHeatmap,
  fetchHistory,
  fetchIndexCards,
  fetchIndexData,
  fetchMarketSnapshot,
  fetchQuote,
  fetchScreenerMetrics,
  fetchSignal,
  fetchSymbols,
  publicGet,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";

/* ── derived UI shapes (mirror web src/lib/psx/types.ts) ── */

export interface UiTicker {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
}

export interface UiIndex {
  name: string;
  value: number;
  change: number;
  changePct: number;
}

/* ── live market snapshot ── */

export function usePsxLiveMarket() {
  return useQuery({
    queryKey: ["psx", "live"],
    queryFn: () => fetchMarketSnapshot(),
    staleTime: 5_000,
    refetchInterval: 30_000,
    // Keep showing the last snapshot while a poll is in flight — no blanking.
    placeholderData: keepPreviousData,
  });
}

/** Alias of usePsxLiveMarket — same query key/cache, so components using
 * either hook share one snapshot request instead of polling twice. */
export function usePsxSnapshot() {
  return usePsxLiveMarket();
}

/** Invalidate the live snapshot (debounced) when the backend refreshes
 * psx_market_snapshot — same Supabase realtime channel as the web app. */
export function usePsxRealtime() {
  const qc = useQueryClient();
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    const channel = supabase
      .channel("psx:market")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "psx_market_snapshot" },
        () => {
          clearTimeout(timer.current);
          timer.current = setTimeout(() => {
            qc.invalidateQueries({ queryKey: ["psx", "live"] });
          }, 10_000);
        },
      )
      .subscribe();

    return () => {
      clearTimeout(timer.current);
      supabase.removeChannel(channel);
    };
  }, [qc]);
}

/* ── derived tickers / movers ── */

function toUiTicker(
  s: ApiMarketSnapshotItem,
  nameMap: Map<string, string>,
  sectorMap: Map<string, string>,
): UiTicker {
  return {
    symbol: s.symbol,
    name: nameMap.get(s.symbol) ?? s.symbol,
    sector: sectorMap.get(s.symbol) ?? "Other",
    price: s.price ?? 0,
    change: s.change ?? 0,
    changePct: s.change_pct ?? 0,
    volume: s.volume ?? 0,
  };
}

export function useMarketTickers(limit = 20): UiTicker[] {
  const { data: snapshot } = usePsxLiveMarket();
  const { data: symbols } = usePsxSymbols();
  if (!snapshot || !symbols) return [];
  const sectorMap = new Map(symbols.map((s) => [s.symbol, s.sector ?? "Other"]));
  const nameMap = new Map(symbols.map((s) => [s.symbol, s.name]));
  return snapshot
    .slice()
    .sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0))
    .slice(0, limit)
    .map((s) => toUiTicker(s, nameMap, sectorMap));
}

export function useMarketMovers(sort: "gainers" | "losers" | "volume", limit = 6): UiTicker[] {
  const { data: snapshot } = usePsxLiveMarket();
  const { data: symbols } = usePsxSymbols();
  if (!snapshot || !symbols) return [];
  const sectorMap = new Map(symbols.map((s) => [s.symbol, s.sector ?? "Other"]));
  const nameMap = new Map(symbols.map((s) => [s.symbol, s.name]));
  const arr = snapshot.map((s) => toUiTicker(s, nameMap, sectorMap));
  if (sort === "gainers")
    return arr
      .filter((s) => s.changePct > 0)
      .sort((a, b) => b.changePct - a.changePct)
      .slice(0, limit);
  if (sort === "losers") return arr.sort((a, b) => a.changePct - b.changePct).slice(0, limit);
  return arr.sort((a, b) => b.volume - a.volume).slice(0, limit);
}

/* ── benchmark index cards ── */

const INDEX_CARD_NAMES: Record<string, string> = {
  KSE100: "KSE-100",
  KSE30: "KSE-30",
  KMI30: "KMI-30",
  ALLSHR: "KSE All Share",
};

/** Latest + previous close per benchmark index from the lightweight
 * /api/index/cards endpoint (one small request instead of four full
 * index-history downloads). */
export function usePsxIndexCards() {
  return useQuery({
    queryKey: ["psx", "index-cards"],
    queryFn: () => fetchIndexCards(),
    staleTime: 30_000,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useIndexCards(): UiIndex[] {
  const { data: cards } = usePsxIndexCards();

  return Object.entries(INDEX_CARD_NAMES).map(([code, name]) => {
    const card = cards?.find((c) => c.code === code);
    if (!card) return { name, value: 0, change: 0, changePct: 0 };
    return {
      name,
      value: card.close,
      change: card.change,
      changePct: card.change_pct,
    };
  });
}

/* ── per-symbol quote / history ── */

export function usePsxQuote(symbol: string | undefined) {
  const qc = useQueryClient();
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "quote", sym],
    queryFn: () => fetchQuote(sym!),
    enabled: !!sym,
    staleTime: 5_000,
    // Paint instantly from the already-loaded market snapshot while the
    // dedicated quote request confirms in the background.
    placeholderData: () => {
      const snapshot = qc.getQueryData<ApiMarketSnapshotItem[]>(["psx", "live"]);
      return snapshot?.find((s) => s.symbol === sym);
    },
  });
}

/** OHLCV history mapped to the shared Candle shape (oldest → newest), ready
 * for the react-native-svg chart components. */
export function usePsxHistory(symbol: string | undefined, days = 180) {
  return useQuery({
    queryKey: ["psx", "history", symbol, days],
    queryFn: async () => {
      const bars = await fetchHistory(symbol!, days);
      return bars
        .slice()
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
        .map<Candle>((b) => ({
          date: b.date,
          t: new Date(b.date).getTime(),
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
          volume: b.volume,
        }));
    },
    enabled: !!symbol,
    staleTime: 60_000_000, // effectively permanent — OHLCV is historical
  });
}

/* ── reference data ── */

export function usePsxSymbols() {
  return useQuery({
    queryKey: ["psx", "symbols"],
    queryFn: () => fetchSymbols(),
    staleTime: 30_000,
  });
}

export function usePsxFundamentals(symbol: string | undefined) {
  return useQuery({
    queryKey: ["psx", "fundamentals", symbol],
    queryFn: () => fetchFundamentals(symbol!),
    enabled: !!symbol,
    staleTime: 60_000,
  });
}

export function usePsxCompanyProfile(symbol: string | undefined) {
  return useQuery({
    queryKey: ["psx", "profile", symbol],
    queryFn: () => fetchCompanyProfile(symbol!),
    enabled: !!symbol,
    staleTime: 300_000,
  });
}

export function usePsxAnnouncements(symbol?: string, limit = 50) {
  return useQuery({
    queryKey: ["psx", "announcements", symbol, limit],
    queryFn: () => fetchAnnouncements(symbol, limit),
    staleTime: 60_000,
  });
}

export function usePsxDividends(symbol: string | undefined) {
  return useQuery({
    queryKey: ["psx", "dividends", symbol],
    queryFn: () => fetchDividends(symbol!),
    enabled: !!symbol,
    staleTime: 300_000,
  });
}

export function usePsxIndexData(code: string | undefined) {
  return useQuery({
    queryKey: ["psx", "index", code],
    queryFn: async () => (await fetchIndexData(code!)).slice().reverse(),
    enabled: !!code,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function usePsxSectors() {
  return useQuery({
    queryKey: ["psx", "sectors"],
    queryFn: async () => (await fetchHeatmap()).sectors,
    staleTime: 15_000,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
  });
}

/** Per-symbol RSI + market cap for the screener/movers tables. Values are
 * null where the backend has insufficient data; callers render a dash. */
export function usePsxScreenerMetrics() {
  return useQuery({
    queryKey: ["psx", "screener-metrics"],
    queryFn: () => fetchScreenerMetrics(),
    staleTime: 120_000,
    refetchInterval: 120_000,
    placeholderData: keepPreviousData,
  });
}

/* ── ML signals ── */

export function usePsxSignal(symbol: string | undefined) {
  return useQuery({
    queryKey: ["psx", "signal", symbol],
    queryFn: () => fetchSignal(symbol!),
    enabled: !!symbol,
    staleTime: 300_000,
  });
}

export function usePsxBatchSignals(limit = 50) {
  return useQuery({
    queryKey: ["psx", "signals", "batch", limit],
    queryFn: () => fetchBatchSignals(limit),
    staleTime: 300_000,
  });
}

/* ── treemap (market depth) ── */
// Shapes mirror web src/lib/psx/types.ts (ApiTreemap*) — not yet in
// @nafaiq/shared, so declared locally. Backend: market_v2.py /market/treemap
// → services/market/treemap.py.

export interface ApiTreemapStock {
  symbol: string;
  name: string;
  sector?: string;
  price: number;
  change_pct: number;
  volume: number;
  /** Real market cap, or null when listed_shares is unknown. Never a proxy. */
  market_cap: number | null;
  /** Value used to size the tile — a real cap or a volume proxy. Not a cap. */
  size_metric: number;
  sizing_basis: "market_cap" | "volume_proxy";
  logoid?: string | null;
}

export interface ApiTreemapSector {
  name: string;
  avg_change_pct: number;
  total_market_cap: number | null;
  total_size_metric: number;
  stock_count: number;
  stocks: ApiTreemapStock[];
}

export interface ApiTreemap {
  as_of: string;
  sectors: ApiTreemapSector[];
  stock_count: number;
}

/** Google-Finance-style treemap: sectors + stock tiles sized by market cap
 * (or a volume proxy), colored by % change. GET /api/market/treemap. */
export function usePsxTreemap() {
  return useQuery({
    queryKey: ["psx", "treemap"],
    queryFn: () => publicGet<ApiTreemap>("/api/market/treemap"),
    staleTime: 15_000,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
  });
}

/* ── unusual activity (volume spikes) ── */
// Mirrors web ApiUnusualActivity (src/lib/psx/client.ts). Backend:
// unusual.py /market/unusual → psx_unusual_activity (VolumeSpikeDetector).

export interface ApiUnusualActivity {
  symbol: string;
  ts: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  volume_ratio: number | null;
  reason: string | null;
}

/** Latest volume spikes / unusual activity. GET /api/market/unusual. */
export function useUnusualActivity(limit = 20) {
  return useQuery({
    queryKey: ["psx", "unusual", limit],
    queryFn: () => publicGet<ApiUnusualActivity[]>(`/api/market/unusual?limit=${limit}`),
    staleTime: 60_000,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
  });
}

/* ── stock search universe (mirror web src/lib/psx/stock-search.ts) ── */

export interface StockSearchResult {
  symbol: string;
  name: string;
  sector: string | null;
  price: number | null;
  change: number | null;
  changePct: number | null;
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

/** Symbols + snapshot joined into a searchable universe (cached queries). */
export function useStockUniverse(): StockSearchResult[] {
  const { data: symbols } = usePsxSymbols();
  const { data: snapshot } = usePsxLiveMarket();
  return buildStockUniverse(symbols, snapshot);
}
