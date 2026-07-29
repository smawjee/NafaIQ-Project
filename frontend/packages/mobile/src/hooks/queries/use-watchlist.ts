// Watchlist hooks. Ported from the web app's src/hooks/psx/use-watchlist.ts,
// minus the demo/Redux branches (mobile has no demo mode): raw symbols come
// straight from Supabase (RLS-scoped to the signed-in user), the enriched
// list from the backend's /api/watchlist, and mutations invalidate both.
import { useCallback } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/use-auth";
import { userGet, userPost, userDelete } from "@/lib/api";
import { supabase } from "@/lib/supabase";

// Writes go through the backend, not Supabase-direct: tighten_grants
// (20260722140000) revoked authenticated INSERT/UPDATE/DELETE on user_watchlist,
// so a direct write now fails permission-denied. The backend endpoint runs as
// service_role and applies require_known_symbol + the max_watchlist quota. The
// SELECT below still works (SELECT was re-granted).
async function upsertSymbol(_userId: string, symbol: string) {
  await userPost("/api/watchlist", { symbol });
}

async function deleteSymbol(_userId: string, symbol: string) {
  await userDelete(`/api/watchlist/${encodeURIComponent(symbol)}`);
}

export function useWatchlist() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const query = useQuery({
    queryKey: ["watchlist"],
    queryFn: async () => {
      const { data } = await supabase
        .from("user_watchlist")
        .select("symbol")
        .order("added_at", { ascending: false });
      return (data ?? []).map((r) => r.symbol);
    },
    enabled: !!user,
    placeholderData: keepPreviousData,
  });

  const add = useCallback(
    async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (!user) throw new Error("Not authenticated");
      // Optimistic: show the symbol immediately; Supabase confirms behind it.
      qc.setQueryData<string[]>(["watchlist"], (prev = []) =>
        prev.includes(sym) ? prev : [sym, ...prev],
      );
      try {
        await upsertSymbol(user.id, sym);
      } catch {
        // Best-effort: the optimistic local update above already applied.
      }
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
    [user, qc],
  );

  const remove = useCallback(
    async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (!user) throw new Error("Not authenticated");
      qc.setQueryData<string[]>(["watchlist"], (prev = []) => prev.filter((s) => s !== sym));
      try {
        await deleteSymbol(user.id, sym);
      } catch {
        // Best-effort: the optimistic local update above already applied.
      }
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
    [user, qc],
  );

  return {
    symbols: query.data ?? [],
    loading: !!user && query.isPending,
    add,
    remove,
  };
}

/* ── enriched watchlist (React Query, authenticated) ── */

export interface EnrichedWatchlistItem {
  symbol: string;
  company_name: string;
  sector: string;
  logoid: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number;
  last_updated: string | null;
}

export function useEnrichedWatchlist(enabled = true) {
  return useQuery<EnrichedWatchlistItem[]>({
    queryKey: ["enriched-watchlist"],
    queryFn: () => userGet<EnrichedWatchlistItem[]>("/api/watchlist"),
    enabled,
    staleTime: 8_000,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
  });
}

export function useAddToWatchlist() {
  const qc = useQueryClient();
  const { user } = useAuth();
  return useMutation({
    mutationFn: async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (!user) throw new Error("Not authenticated");
      await upsertSymbol(user.id, sym);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  const { user } = useAuth();
  return useMutation({
    mutationFn: async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (!user) throw new Error("Not authenticated");
      await deleteSymbol(user.id, sym);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
  });
}
