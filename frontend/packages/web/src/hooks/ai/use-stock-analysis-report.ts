/**
 * useStockAnalysisReport — per-symbol educational analysis
 * (`POST /api/ai/report/stock/{symbol}`). The backend caches the response by
 * (symbol, trading_date), so a single query per symbol per day covers all
 * users. `staleTime: 24h` matches the server cache and prevents re-fires on
 * remount within the same day.
 */
import { useQuery } from "@tanstack/react-query";
import { useLang } from "@/hooks/use-lang";
import { generateStockReport, type ReportResponse, ReportError } from "@/lib/ai/reports-client";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function useStockAnalysisReport(symbol: string | undefined | null) {
  const { lang } = useLang();
  const upper = symbol?.trim().toUpperCase() ?? "";
  return useQuery<ReportResponse, ReportError>({
    queryKey: ["ai", "stock-analysis", upper, lang],
    queryFn: () => generateStockReport(upper, lang),
    enabled: upper.length > 0,
    staleTime: ONE_DAY_MS,
    gcTime: ONE_DAY_MS,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchInterval: false,
    retry: (failureCount, err) => {
      if (err instanceof ReportError) {
        return err.code === "network" && failureCount < 2;
      }
      return false;
    },
  });
}
