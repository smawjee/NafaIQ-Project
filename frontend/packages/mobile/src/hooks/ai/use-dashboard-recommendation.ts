// Dashboard daily nudge — day-cached per user. refresh() regenerates and COSTS
// report quota (429 when out), so it fires only on a deliberate user tap.
// Ported from web hooks/ai/use-dashboard-recommendation.ts.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReportResponse } from "@nafaiq/shared";

import { useLang } from "@/hooks/use-lang";
import { getDashboardRecommendation, ReportError } from "@/lib/ai/reports-client";

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
    refetchOnReconnect: false,
    refetchInterval: false,
    retry: (failureCount, err) =>
      err instanceof ReportError && err.code === "network" && failureCount < 2,
  });

  const refresh = useMutation<ReportResponse, ReportError>({
    mutationFn: () => getDashboardRecommendation(lang, true),
    retry: false,
    onSuccess: (data) => queryClient.setQueryData(queryKey, data),
  });

  return {
    ...query,
    refresh: refresh.mutate,
    isRefreshing: refresh.isPending,
    refreshError: refresh.error,
  };
}
