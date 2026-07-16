/**
 * useDashboardRecommendation — daily-cached cross-domain nudge
 * (`GET /api/ai/report/dashboard-recommendation`). Auto-loads on page open
 * (per product decision); the server caches by trading date so the same user
 * within a day reads from cache. `enabled` is the dismiss switch — once the
 * user dismisses, the query stops refetching for the rest of the session.
 */
import { useQuery } from "@tanstack/react-query";
import { useLang } from "@/hooks/use-lang";
import {
  getDashboardRecommendation,
  type ReportResponse,
  ReportError,
} from "@/lib/ai/reports-client";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function useDashboardRecommendation(enabled = true) {
  const { lang } = useLang();
  return useQuery<ReportResponse, ReportError>({
    queryKey: ["ai", "dashboard-recommendation", lang],
    queryFn: () => getDashboardRecommendation(lang),
    enabled,
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
