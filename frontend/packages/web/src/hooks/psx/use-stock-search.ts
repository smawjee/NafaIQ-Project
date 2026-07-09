import { useDeferredValue, useMemo } from "react";
import { usePsxSymbols, usePsxLiveMarket } from "@/hooks/psx/use-psx";
import { buildStockUniverse, matchStocks, type StockSearchResult } from "@/lib/psx/stock-search";

export interface UseStockSearch {
  results: StockSearchResult[];
  loading: boolean;
  error: boolean;
  isEmpty: boolean;
  hasQuery: boolean;
}

/**
 * Shared stock-search hook powering both the Watchlist add dropdown and the
 * global search bar. Fetches the symbol universe + batched prices once (React
 * Query cached), debounces via useDeferredValue, and filters on the client.
 */
export function useStockSearch(query: string, limit = 50): UseStockSearch {
  const { data: symbols, isLoading, isError } = usePsxSymbols();
  const { data: snapshot } = usePsxLiveMarket();
  const deferredQuery = useDeferredValue(query);

  const universe = useMemo(() => buildStockUniverse(symbols, snapshot), [symbols, snapshot]);

  const results = useMemo(
    () => matchStocks(universe, deferredQuery, limit),
    [universe, deferredQuery, limit],
  );

  const hasQuery = deferredQuery.trim().length > 0;
  return {
    results,
    loading: isLoading,
    error: isError,
    isEmpty: !isLoading && !isError && results.length === 0,
    hasQuery,
  };
}
