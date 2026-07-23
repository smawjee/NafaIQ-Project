import { useEffect, useMemo, useRef } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Candle } from "@/lib/data";
import type {
  ApiMarketSnapshotItem,
  SignalHorizon,
  UiTicker,
  UiIndex,
  UiSector,
} from "@/lib/psx/types";
import { supabase } from "@/integrations/supabase/client";
import {
  fetchMarketSnapshot,
  fetchQuote,
  fetchHistory,
  fetchSymbols,
  fetchFundamentals,
  fetchProfile,
  fetchAnnouncements,
  fetchIndexData,
  fetchIndexCards,
  fetchScreenerMetrics,
  fetchTreemap,
  fetchSignal,
  fetchSignalV4,
  fetchBatchSignals,
  fetchSignalV2,
  fetchBatchSignalsV2,
  fetchSignalTrackRecord,
} from "@/lib/psx/client";

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

/**
 * Phase 0 / B8: scope the realtime channel to the watchlist (or to a single
 * symbol, in the per-stock detail page). With 500+ symbols, listening to
 * every change on `psx_market_snapshot` floods the global invalidation
 * queue; this filter keeps the channel narrow.
 *
 * If `watchlist` is empty, the channel still subscribes (no filter) so
 * `/psx` and the global ticker strip still update on every DPS poll.
 */
export function usePsxRealtime(watchlist?: string[] | null) {
  const qc = useQueryClient();
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const symKey = (watchlist ?? [])
    .map((s) => s.toUpperCase())
    .filter(Boolean)
    .sort()
    .join(",");

  useEffect(() => {
    const symbols = symKey ? symKey.split(",") : [];
    // Supabase realtime filter: "symbol=in.(HBL,OGDC,...)" with values quoted
    // to survive any reserved characters. An empty `symbols` array means
    // "no filter" — the channel still receives every change.
    const filter =
      symbols.length > 0
        ? `symbol=in.(${symbols.map((s) => `"${s.replace(/"/g, "")}"`).join(",")})`
        : undefined;

    const channel = supabase
      .channel("psx:market")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "psx_market_snapshot",
          ...(filter ? { filter } : {}),
        },
        (payload) => {
          const sym = (payload.new as { symbol?: string } | undefined)?.symbol;
          // Phase 0 / B8: splice the new row into the per-symbol + watchlist
          // caches in place so the UI updates inside the debounce window
          // without waiting for a refetch.
          if (sym) {
            qc.setQueryData(["psx", "quote", sym], payload.new);
            qc.setQueryData(["psx", "live"], (prev: unknown) => {
              if (!Array.isArray(prev)) return prev;
              const nextRow = payload.new as ApiMarketSnapshotItem;
              let found = false;
              const next = (prev as ApiMarketSnapshotItem[]).map((row) => {
                if (row.symbol !== sym) return row;
                found = true;
                return { ...row, ...nextRow };
              });
              return found ? next : [...next, nextRow];
            });
            qc.setQueryData(["enriched-watchlist"], (prev: unknown) => {
              if (!Array.isArray(prev)) return prev;
              return (prev as { symbol: string }[]).map((row) =>
                row.symbol === sym ? { ...row, ...(payload.new as object) } : row,
              );
            });
          }
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
  }, [qc, symKey]);
}

export function useMarketTickers(limit = 20): UiTicker[] {
  const { data: snapshot } = usePsxLiveMarket();
  const { data: symbols } = usePsxSymbols();
  return useMemo(() => {
    if (!snapshot || !symbols) return [];
    const sectorMap = new Map(symbols.map((s) => [s.symbol, s.sector ?? "Other"]));
    const nameMap = new Map(symbols.map((s) => [s.symbol, s.name]));
    return snapshot
      .slice()
      .sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0))
      .slice(0, limit)
      .map((s) => ({
        symbol: s.symbol,
        name: nameMap.get(s.symbol) ?? s.symbol,
        sector: sectorMap.get(s.symbol) ?? "Other",
        price: s.price ?? 0,
        change: s.change ?? 0,
        changePct: s.change_pct ?? 0,
        volume: s.volume ?? 0,
      }));
  }, [snapshot, symbols, limit]);
}

export function useMarketMovers(
  sort: "gainers" | "losers" | "volume" | "abs",
  limit = 6,
): UiTicker[] {
  const { data: snapshot } = usePsxLiveMarket();
  const { data: symbols } = usePsxSymbols();
  if (!snapshot || !symbols) return [];
  const sectorMap = new Map(symbols.map((s) => [s.symbol, s.sector ?? "Other"]));
  const nameMap = new Map(symbols.map((s) => [s.symbol, s.name]));
  const arr = snapshot.map((s) => ({
    symbol: s.symbol,
    name: nameMap.get(s.symbol) ?? s.symbol,
    sector: sectorMap.get(s.symbol) ?? "Other",
    price: s.price ?? 0,
    change: s.change ?? 0,
    changePct: s.change_pct ?? 0,
    volume: s.volume ?? 0,
  }));
  if (sort === "gainers")
    return arr
      .filter((s) => s.changePct > 0)
      .sort((a, b) => b.changePct - a.changePct)
      .slice(0, limit);
  if (sort === "losers") return arr.sort((a, b) => a.changePct - b.changePct).slice(0, limit);
  // "abs": biggest movers in either direction. Distinct from "gainers", which
  // filters to changePct > 0 and so can never surface a faller.
  if (sort === "abs")
    return arr.sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct)).slice(0, limit);
  return arr.sort((a, b) => b.volume - a.volume).slice(0, limit);
}

export const INDEX_CARD_NAMES: Record<string, string> = {
  KSE100: "KSE-100",
  KSE100PR: "KSE-100 PR",
  KSE30: "KSE-30",
  KMI30: "KMI-30",
  KMIALLSHR: "KMI All Share",
  ALLSHR: "KSE All Share",
  BKTI: "BKTI",
  OGTI: "OGTI",
  PSXDIV20: "PSX Div 20",
  UPP9: "UPP9",
  NITPGI: "NITPGI",
  NBPPGI: "NBPPGI",
  MZNPI: "MZNPI",
  JSMFI: "JSMFI",
  ACI: "ACI",
  JSGBKTI: "JSGBKTI",
  HBLTTI: "HBLTTI",
  MII30: "MII30",
};

export const INDEX_CODE_BY_NAME = Object.fromEntries(
  Object.entries(INDEX_CARD_NAMES).map(([code, name]) => [name, code]),
) as Record<string, string>;

export function indexNameToCode(name: string | undefined) {
  return name ? INDEX_CODE_BY_NAME[name] : undefined;
}

// Priority 4 — the dashboard's default cards. The PSX index grid renders
// these first when the user hasn't expanded the "show all" view.
const PRIORITY_INDEX_CODES = ["KSE100", "KSE30", "KMI30", "ALLSHR"] as const;

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

export function useIndexCards(limit = 4): UiIndex[] {
  const { data: cards } = usePsxIndexCards();

  const orderedCodes = [
    ...PRIORITY_INDEX_CODES,
    ...Object.keys(INDEX_CARD_NAMES).filter(
      (c) => !(PRIORITY_INDEX_CODES as readonly string[]).includes(c),
    ),
  ].slice(0, limit);

  return orderedCodes.map((code) => {
    const name = INDEX_CARD_NAMES[code];
    const card = cards?.find((c) => c.code === code);
    if (!card) return { code, name, value: 0, change: 0, changePct: 0, date: null };
    return {
      code,
      name,
      value: card.close,
      change: card.change,
      changePct: card.change_pct,
      date: card.date,
    };
  });
}

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

export function usePsxHistory(symbol: string | undefined, days = 180) {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "history", sym, days],
    queryFn: async () => {
      const bars = await fetchHistory(sym!, days);
      return bars
        .slice()
        .reverse()
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
    // Keep previous data while the new symbol's bars are fetching. Without
    // this, switching stocks would unmount the chart and remount it once the
    // fetch resolves, causing a flash of empty state and a possible length
    // mismatch between `data` and `maSeries` that Recharts throws on.
    placeholderData: keepPreviousData,
  });
}

export function usePsxSymbols() {
  return useQuery({
    queryKey: ["psx", "symbols"],
    queryFn: () => fetchSymbols(),
    staleTime: 30_000,
  });
}

export function usePsxFundamentals(symbol: string | undefined) {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "fundamentals", sym],
    queryFn: () => fetchFundamentals(sym!),
    enabled: !!symbol,
    staleTime: 60_000,
  });
}

export function usePsxProfile(symbol: string | undefined) {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "profile", sym],
    queryFn: () => fetchProfile(sym!),
    enabled: !!symbol,
    staleTime: 300_000,
  });
}

export function usePsxAnnouncements(symbol?: string, limit = 50) {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "announcements", sym, limit],
    queryFn: () => fetchAnnouncements(sym, limit),
    staleTime: 60_000,
  });
}

export function usePsxIndexData(code: string | undefined) {
  const sym = code?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "index", sym],
    queryFn: async () => (await fetchIndexData(sym!)).slice().reverse(),
    enabled: !!code,
    staleTime: 60_000,
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

export function usePsxSignal(symbol: string | undefined) {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "signal", sym],
    queryFn: () => fetchSignal(sym!),
    enabled: !!symbol,
    staleTime: 300_000,
  });
}

export function usePsxSignalV4(symbol: string | undefined) {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "signal", "v4", sym],
    queryFn: () => fetchSignalV4(sym!),
    enabled: !!symbol,
    staleTime: 300_000,
  });
}

export function usePsxSignalV2(symbol: string | undefined, horizon: SignalHorizon = "20D") {
  const sym = symbol?.toUpperCase();
  return useQuery({
    queryKey: ["psx", "signal", "v2", sym, horizon],
    queryFn: () => fetchSignalV2(sym!, horizon),
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

export function usePsxSignalTrackRecord() {
  return useQuery({
    queryKey: ["psx", "signals", "v2", "track-record"],
    queryFn: () => fetchSignalTrackRecord(),
    staleTime: 3_600_000, // outcomes change once a day at most
  });
}

export function usePsxBatchSignalsV2(limit = 50, horizon: SignalHorizon = "20D") {
  return useQuery({
    queryKey: ["psx", "signals", "v2", "batch", limit, horizon],
    queryFn: () => fetchBatchSignalsV2(limit, horizon),
    staleTime: 300_000,
  });
}

/** Google-Finance-style treemap payload: sectors → stocks sized by market
 * cap, colored by % change. Polled at 2m with a 60s stale window — the
 * payload is heavy (~500 stocks) so we deliberately don't refetch on every
 * `usePsxRealtime` tick. */
export function usePsxTreemap() {
  return useQuery({
    queryKey: ["psx", "treemap"],
    queryFn: () => fetchTreemap(),
    staleTime: 60_000,
    refetchInterval: 120_000,
    placeholderData: keepPreviousData,
  });
}
