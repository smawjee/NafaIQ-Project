import { useCallback, useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { userGet, userPost, userDelete } from "@/lib/psx/client";
import { useAuth } from "@/hooks/use-auth";
import { isDemoUser } from "@/lib/demo";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addWatchlistSymbol,
  removeWatchlistSymbol,
  selectWatchlistSymbols,
} from "@/store/watchlist";

export function useWatchlist() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const dispatch = useAppDispatch();
  // Demo and anonymous users live entirely in the local Redux store —
  // their watchlist never touches Supabase.
  const useLocal = !user || isDemoUser(user);
  const localSymbols = useAppSelector(selectWatchlistSymbols);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (useLocal) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const { data } = await supabase
        .from("user_watchlist")
        .select("symbol")
        .order("added_at", { ascending: false });
      setSymbols((data ?? []).map((r) => r.symbol));
    } catch {
      setSymbols([]);
    } finally {
      setLoading(false);
    }
  }, [useLocal]);

  useEffect(() => {
    load();
  }, [load]);

  const add = useCallback(
    async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (useLocal) {
        dispatch(addWatchlistSymbol(sym));
        return;
      }
      setSymbols((prev) => {
        if (prev.includes(sym)) return prev;
        return [...prev, sym];
      });
      try {
        // Via the backend, not Supabase-direct: tighten_grants
        // (20260722140000) revoked authenticated INSERT/UPDATE on
        // user_watchlist, so a direct upsert now fails permission-denied. The
        // backend endpoint runs as service_role and applies require_known_symbol
        // + the max_watchlist quota.
        await userPost("/api/watchlist", { symbol: sym });
      } catch {
        // Best-effort: the optimistic local update above already applied.
      }
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
    [useLocal, user, qc, dispatch],
  );

  const remove = useCallback(
    async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (useLocal) {
        dispatch(removeWatchlistSymbol(sym));
        return;
      }
      setSymbols((prev) => prev.filter((s) => s !== sym));
      try {
        await userDelete(`/api/watchlist/${encodeURIComponent(sym)}`);
      } catch {
        // Best-effort: the optimistic local update above already applied.
      }
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
    [useLocal, user, qc, dispatch],
  );

  return {
    symbols: useLocal ? localSymbols : symbols,
    loading: useLocal ? false : loading,
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
      await userPost("/api/watchlist", { symbol: sym });
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
      await userDelete(`/api/watchlist/${encodeURIComponent(sym)}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
  });
}
