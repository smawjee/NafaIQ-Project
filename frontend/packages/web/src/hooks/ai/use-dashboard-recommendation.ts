/**
 * useDashboardRecommendation — daily-cached cross-domain nudge
 * (`GET /api/ai/report/dashboard-recommendation`). Auto-loads on page open
 * (per product decision); the server caches by trading date so the same user
 * within a day reads from cache. `enabled` is the dismiss switch — once the
 * user dismisses, the query stops refetching for the rest of the session.
 *
 * `refresh()` is the manual regenerate. It is a MUTATION, not a refetch, and
 * deliberately not wired to any automatic trigger: the server treats
 * `?refresh=true` as a real generation and charges the report quota for it, so
 * it must fire only on a click. Everything auto (mount, focus, reconnect,
 * interval, retry) stays off and reads the cached row for free.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLang } from "@/hooks/use-lang";
import {
  getDashboardRecommendation,
  type ReportResponse,
  ReportError,
} from "@/lib/ai/reports-client";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function useDashboardRecommendation(enabled = true) {
  const { lang } = useLang();
  const queryClient = useQueryClient();
  const queryKey = ["ai", "dashboard-recommendation", lang];

  const query = useQuery<ReportResponse, ReportError>({
    queryKey,
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

  const refresh = useMutation<ReportResponse, ReportError>({
    mutationFn: () => getDashboardRecommendation(lang, true),
    // No retry: each attempt costs another quota unit. A failed refresh is the
    // user's to retry, not ours.
    retry: false,
    // Seed the query cache directly rather than invalidating — invalidating
    // would trigger a second (free, cached) GET for a report we already hold.
    onSuccess: (data) => queryClient.setQueryData(queryKey, data),
  });

  return {
    ...query,
    refresh: refresh.mutate,
    isRefreshing: refresh.isPending,
    refreshError: refresh.error,
  };
}
