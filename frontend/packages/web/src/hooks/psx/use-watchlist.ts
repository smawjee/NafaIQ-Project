import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { userGet } from "@/lib/psx/client";
import { useAuth } from "@/hooks/use-auth";

const DEFAULT_WATCHLIST = ["HBL", "ENGRO", "LUCK", "OGDC"];
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || "demo@nafaiq.com";

export function useWatchlist() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isDemo = user?.email === DEMO_EMAIL;
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_WATCHLIST);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (!user || isDemo) {
        setSymbols(DEFAULT_WATCHLIST);
        return;
      }
      const { data } = await supabase
        .from("user_watchlist")
        .select("symbol")
        .order("added_at", { ascending: false });
      setSymbols((data ?? []).map((r) => r.symbol));
    } catch {
      setSymbols(user && !isDemo ? [] : DEFAULT_WATCHLIST);
    } finally {
      setLoading(false);
    }
  }, [isDemo, user]);

  useEffect(() => {
    load();
  }, [load]);

  const add = useCallback(async (symbol: string) => {
    const sym = symbol.toUpperCase().trim();
    setSymbols((prev) => {
      if (prev.includes(sym)) return prev;
      return [...prev, sym];
    });
    try {
      if (!user || isDemo) return;
      await supabase
        .from("user_watchlist")
        .upsert(
          { symbol: sym, user_id: user.id },
          { onConflict: "user_id,symbol" },
        );
    } catch {
      // Demo and anonymous users intentionally remain local-only.
    }
    qc.invalidateQueries({ queryKey: ["watchlist"] });
    qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
  }, [isDemo, user, qc]);

  const remove = useCallback(async (symbol: string) => {
    const sym = symbol.toUpperCase().trim();
    setSymbols((prev) => prev.filter((s) => s !== sym));
    try {
      if (!user || isDemo) return;
      await supabase
        .from("user_watchlist")
        .delete()
        .eq("user_id", user.id)
        .eq("symbol", sym);
    } catch {
      // Demo and anonymous users intentionally remain local-only.
    }
    qc.invalidateQueries({ queryKey: ["watchlist"] });
    qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
  }, [isDemo, user, qc]);

  return { symbols, loading, add, remove };
}

/* ── enriched watchlist (React Query, authenticated) ── */

export interface EnrichedWatchlistItem {
  symbol: string;
  company_name: string;
  sector: string;
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
  });
}

export function useAddToWatchlist() {
  const qc = useQueryClient();
  const { user } = useAuth();
  return useMutation({
    mutationFn: async (symbol: string) => {
      const sym = symbol.toUpperCase().trim();
      if (!user) throw new Error("Not authenticated");
      await supabase
        .from("user_watchlist")
        .upsert(
          { symbol: sym, user_id: user.id },
          { onConflict: "user_id,symbol" },
        );
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
      await supabase
        .from("user_watchlist")
        .delete()
        .eq("user_id", user.id)
        .eq("symbol", sym);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["enriched-watchlist"] });
    },
  });
}
