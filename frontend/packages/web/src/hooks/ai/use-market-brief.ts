/**
 * useMarketBrief — shared daily market brief (`GET /api/ai/report/market-brief`).
 * The report is SHARED (no user data), and the server caches it per trading
 * date, so every reader within a day hits the cache rather than the model.
 */
import { useQuery } from "@tanstack/react-query";
import { useLang } from "@/hooks/use-lang";
import { getMarketBrief, type ReportResponse, ReportError } from "@/lib/ai/reports-client";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function useMarketBrief(enabled = true) {
  const { lang } = useLang();
  return useQuery<ReportResponse, ReportError>({
    queryKey: ["ai", "market-brief", lang],
    queryFn: () => getMarketBrief(lang),
    enabled,
    staleTime: ONE_DAY_MS,
    gcTime: ONE_DAY_MS,
    retry: (failureCount, err) => {
      if (err instanceof ReportError) {
        return err.code === "network" && failureCount < 2;
      }
      return false;
    },
  });
}
