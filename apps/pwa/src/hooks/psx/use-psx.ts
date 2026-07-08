import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Candle } from "@/lib/data";
import type { UiTicker, UiIndex, UiSector } from "@/lib/psx/types";
import { supabase } from "@/integrations/supabase/client";
import {
  fetchMarketSnapshot,
  fetchQuote,
  fetchHistory,
  fetchSymbols,
  fetchFundamentals,
  fetchProfile,
  fetchAnnouncements,
  fetchDividends,
  fetchIndexData,
  fetchSectors,
  fetchSignal,
  fetchBatchSignals,
} from "@/lib/psx/client";

export function usePsxLiveMarket() {
  return useQuery({
    queryKey: ["psx", "live"],
    queryFn: () => fetchMarketSnapshot(),
    staleTime: 5_000,
    refetchInterval: 8_000,
  });
}

export function usePsxRealtime() {
  const qc = useQueryClient();

  useEffect(() => {
    const channel = supabase
      .channel("psx:market")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "psx_market_snapshot" },
        () => {
          qc.invalidateQueries({ queryKey: ["psx", "live"] });
        },
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [qc]);
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
    .map((s) => ({
      symbol: s.symbol,
      name: nameMap.get(s.symbol) ?? s.symbol,
      sector: sectorMap.get(s.symbol) ?? "Other",
      price: s.price ?? 0,
      change: s.change ?? 0,
      changePct: s.change_pct ?? 0,
      volume: s.volume ?? 0,
    }));
}

export function useMarketMovers(
  sort: "gainers" | "losers" | "volume",
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
  if (sort === "losers")
    return arr.sort((a, b) => a.changePct - b.changePct).slice(0, limit);
  return arr.sort((a, b) => b.volume - a.volume).slice(0, limit);
}

export function useMarketTickerForSymbol(
  symbol: string | undefined,
): UiTicker | null {
  const { data: snapshot } = usePsxLiveMarket();
  if (!snapshot || !symbol) return null;
  const found = snapshot.find((s) => s.symbol === symbol.toUpperCase());
  if (!found) return null;
  return {
    symbol: found.symbol,
    name: found.symbol,
    sector: "Other",
    price: found.price ?? 0,
    change: found.change ?? 0,
    changePct: found.change_pct ?? 0,
    volume: found.volume ?? 0,
  };
}

export function useIndexCards(): UiIndex[] {
  const { data: kse1 } = usePsxIndexData("KSE100");
  const { data: kse3 } = usePsxIndexData("KSE30");
  const { data: kmi } = usePsxIndexData("KMI30");
  const { data: ash } = usePsxIndexData("ALLSHR");

  function toUi(
    data: { close: number; date: string; volume: number | null }[] | undefined,
    name: string,
  ): UiIndex {
    if (!data || data.length < 2)
      return { name, value: 0, change: 0, changePct: 0 };
    const latest = data[data.length - 1].close;
    const prev = data[data.length - 2].close;
    return {
      name,
      value: latest,
      change: +(latest - prev).toFixed(2),
      changePct: +(prev !== 0 ? ((latest - prev) / prev) * 100 : 0).toFixed(2),
    };
  }

  return [
    toUi(kse1, "KSE-100"),
    toUi(kse3, "KSE-30"),
    toUi(kmi, "KMI-30"),
    toUi(ash, "KSE All Share"),
  ];
}

export function usePsxSnapshot() {
  return useQuery({
    queryKey: ["psx", "snapshot"],
    queryFn: () => fetchMarketSnapshot(),
    staleTime: 5_000,
    refetchInterval: 15_000,
  });
}

export function usePsxQuote(symbol: string | undefined) {
  return useQuery({
    queryKey: ["psx", "quote", symbol],
    queryFn: () => fetchQuote(symbol!),
    enabled: !!symbol,
    staleTime: 5_000,
  });
}

export function usePsxHistory(symbol: string | undefined, days = 180) {
  return useQuery({
    queryKey: ["psx", "history", symbol, days],
    queryFn: async () => {
      const bars = await fetchHistory(symbol!, days);
      return bars.map<Candle>((b) => ({
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

export function usePsxProfile(symbol: string | undefined) {
  return useQuery({
    queryKey: ["psx", "profile", symbol],
    queryFn: () => fetchProfile(symbol!),
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
    queryFn: () => fetchIndexData(code!),
    enabled: !!code,
    staleTime: 60_000,
  });
}

export function usePsxSectors() {
  return useQuery({
    queryKey: ["psx", "sectors"],
    queryFn: () => fetchSectors(),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

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
