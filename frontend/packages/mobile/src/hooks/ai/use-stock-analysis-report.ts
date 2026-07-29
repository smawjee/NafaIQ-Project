// Per-symbol stock analysis report — day-stable, so a query (not a mutation).
// Ported from web hooks/ai/use-stock-analysis-report.ts.
import { useQuery } from "@tanstack/react-query";
import type { ReportResponse } from "@nafaiq/shared";

import { useLang } from "@/hooks/use-lang";
import { generateStockReport, ReportError } from "@/lib/ai/reports-client";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function useStockAnalysisReport(symbol: string | undefined, enabled = true) {
  const { lang } = useLang();
  return useQuery<ReportResponse, ReportError>({
    queryKey: ["ai", "stock-report", symbol, lang],
    queryFn: () => generateStockReport(symbol as string, lang),
    enabled: enabled && !!symbol,
    staleTime: ONE_DAY_MS,
    gcTime: ONE_DAY_MS,
    refetchOnMount: false,
    refetchOnReconnect: false,
    refetchInterval: false,
    retry: (failureCount, err) =>
      err instanceof ReportError && err.code === "network" && failureCount < 2,
  });
}
