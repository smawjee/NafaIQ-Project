import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLang } from "@/hooks/use-lang";
import { getMarketBrief, type ReportResponse, ReportError } from "@/lib/ai/reports-client";

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function useMarketBrief(enabled = true) {
  const { lang } = useLang();
  const queryClient = useQueryClient();
  const queryKey = ["ai", "market-brief", lang];

  const query = useQuery<ReportResponse, ReportError>({
    queryKey,
    queryFn: () => getMarketBrief(lang),
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
    mutationFn: () => getMarketBrief(lang, true),
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