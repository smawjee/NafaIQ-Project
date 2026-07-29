// Dividends — public GET /api/dividends (all) and /api/dividends/{symbol}.
// Reuses the shared ApiDividendEvent contract.
import type { ApiDividendEvent } from "@nafaiq/shared";
import { useQuery } from "@tanstack/react-query";

import { fetchDividends, publicGet } from "@/lib/api";

export type { ApiDividendEvent };

export function useDividends(enabled: boolean = true) {
  return useQuery<ApiDividendEvent[]>({
    queryKey: ["dividends", "all"],
    queryFn: () => publicGet<ApiDividendEvent[]>("/api/dividends"),
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function useSymbolDividends(symbol: string | undefined) {
  return useQuery<ApiDividendEvent[]>({
    queryKey: ["dividends", "symbol", symbol],
    queryFn: () => fetchDividends(symbol as string),
    enabled: !!symbol,
    staleTime: 10 * 60_000,
  });
}
