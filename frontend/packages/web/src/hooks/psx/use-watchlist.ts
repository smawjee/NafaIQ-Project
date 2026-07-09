import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";

const DEFAULT_WATCHLIST = ["HBL", "ENGRO", "LUCK", "OGDC"];
const DEMO_EMAIL = import.meta.env.VITE_DEMO_EMAIL || "demo@nafaiq.com";

export function useWatchlist() {
  const { user } = useAuth();
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
    const sym = symbol.toUpperCase();
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
  }, [isDemo, user]);

  const remove = useCallback(async (symbol: string) => {
    const sym = symbol.toUpperCase();
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
  }, [isDemo, user]);

  return { symbols, loading, add, remove };
}
