import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";

export function useWatchlist() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data: session } = await supabase.auth.getSession();
      if (!session?.session) {
        setSymbols(["HBL", "ENGRO", "LUCK", "OGDC"]);
        setLoading(false);
        return;
      }
      const { data } = await supabase
        .from("user_watchlist")
        .select("symbol")
        .order("added_at", { ascending: false });
      if (data) {
        setSymbols(data.map((r) => r.symbol));
      } else {
        setSymbols(["HBL", "ENGRO", "LUCK", "OGDC"]);
      }
    } catch {
      setSymbols(["HBL", "ENGRO", "LUCK", "OGDC"]);
    }
    setLoading(false);
  }, []);

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
      const { data: session } = await supabase.auth.getSession();
      if (!session?.session) return;
      await supabase
        .from("user_watchlist")
        .upsert(
          { symbol: sym, user_id: session.session.user.id },
          { onConflict: "user_id,symbol" },
        );
    } catch {
      // fallback to local state only
    }
  }, []);

  const remove = useCallback(async (symbol: string) => {
    const sym = symbol.toUpperCase();
    setSymbols((prev) => prev.filter((s) => s !== sym));
    try {
      const { data: session } = await supabase.auth.getSession();
      if (!session?.session) return;
      await supabase
        .from("user_watchlist")
        .delete()
        .eq("user_id", session.session.user.id)
        .eq("symbol", sym);
    } catch {
      // fallback to local state only
    }
  }, []);

  return { symbols, loading, add, remove };
}
