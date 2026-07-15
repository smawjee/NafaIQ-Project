import { useQuery } from "@tanstack/react-query";
import {
  fetchAnnualFinancials,
  fetchFilings,
  fetchFundNavHistory,
  fetchLatestNews,
  fetchMacroFx,
  fetchMacroRates,
  fetchMutualFunds,
  fetchNews,
  fetchPolicyRate,
  fetchQuarterlyFinancials,
  fetchUnusualActivity,
  type ApiFinancialAnnual,
  type ApiFinancialQuarterly,
  type ApiFiling,
  type ApiFundNavHistory,
  type ApiMacroFx,
  type ApiMacroRate,
  type ApiMutualFund,
  type ApiNewsItem,
  type ApiUnusualActivity,
} from "@/lib/psx/client";

/** Latest KIBOR 3-month rate (1-hour stale — SBP publishes daily). */
export function useKibor(tenor: string = "3M") {
  return useQuery({
    queryKey: ["macro", "kibor", tenor],
    queryFn: () => fetchMacroRates(`KIBOR_${tenor}`),
    staleTime: 60 * 60 * 1000,
  });
}

/** Latest USD/PKR + EUR/PKR + GBP/PKR (1-hour stale). */
export function useMacroFx() {
  return useQuery({
    queryKey: ["macro", "fx"],
    queryFn: () => fetchMacroFx(),
    staleTime: 60 * 60 * 1000,
  });
}

/** Latest SBP policy rate (1-hour stale). */
export function usePolicyRate() {
  return useQuery<ApiMacroRate>({
    queryKey: ["macro", "policy-rate"],
    queryFn: () => fetchPolicyRate(),
    staleTime: 60 * 60 * 1000,
  });
}

export function useNews(symbol: string | undefined, limit = 20) {
  return useQuery<ApiNewsItem[]>({
    queryKey: ["news", symbol, limit],
    queryFn: () => fetchNews(symbol, limit),
    enabled: !!symbol,
    staleTime: 60 * 1000,
  });
}

export function useLatestNews(limit = 10) {
  return useQuery<ApiNewsItem[]>({
    queryKey: ["news", "latest", limit],
    queryFn: () => fetchLatestNews(limit),
    staleTime: 60 * 1000,
  });
}

export function useFilings(symbol: string | undefined, limit = 50) {
  return useQuery<ApiFiling[]>({
    queryKey: ["filings", symbol, limit],
    queryFn: () => fetchFilings(symbol!, limit),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}

export function useUnusualActivity(limit = 20) {
  return useQuery<ApiUnusualActivity[]>({
    queryKey: ["market", "unusual", limit],
    queryFn: () => fetchUnusualActivity(limit),
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useAnnualFinancials(symbol: string | undefined, limit = 10) {
  return useQuery<ApiFinancialAnnual[]>({
    queryKey: ["financials", "annual", symbol, limit],
    queryFn: () => fetchAnnualFinancials(symbol!, limit),
    enabled: !!symbol,
    staleTime: 24 * 60 * 60 * 1000, // weekly refresh — once-per-day is fine
  });
}

export function useQuarterlyFinancials(symbol: string | undefined, limit = 20) {
  return useQuery<ApiFinancialQuarterly[]>({
    queryKey: ["financials", "quarterly", symbol, limit],
    queryFn: () => fetchQuarterlyFinancials(symbol!, limit),
    enabled: !!symbol,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

// === Mutual Funds (MUFAP) ===

export function useMutualFunds() {
  return useQuery<ApiMutualFund[]>({
    queryKey: ["funds", "mutual-funds"],
    queryFn: () => fetchMutualFunds(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useFundNavHistory(fundCode: string | undefined, limit = 100) {
  return useQuery<ApiFundNavHistory[]>({
    queryKey: ["funds", "nav-history", fundCode, limit],
    queryFn: () => fetchFundNavHistory(fundCode!, limit),
    enabled: !!fundCode,
    staleTime: 5 * 60 * 1000,
  });
}
