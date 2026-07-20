// Macro data — public GET /api/macro/rates, /api/macro/fx, /api/macro/policy-rate.
// Backend returns raw rows / computed maps; typed best-effort.
import { useQuery } from "@tanstack/react-query";

import { publicGet } from "@/lib/api";

export interface MacroRate {
  series?: string;
  date: string;
  value: number;
  [key: string]: unknown;
}

export interface FxRate {
  currency: string;
  buying?: number | null;
  selling?: number | null;
  [key: string]: unknown;
}

export interface PolicyRate {
  date: string;
  rate: number;
  [key: string]: unknown;
}

export function useMacroRates(series?: string, limit: number = 60, enabled: boolean = true) {
  const params = new URLSearchParams();
  if (series) params.set("series", series);
  params.set("limit", String(limit));
  return useQuery<MacroRate[]>({
    queryKey: ["macro", "rates", series ?? "all", limit],
    queryFn: () => publicGet<MacroRate[]>(`/api/macro/rates?${params.toString()}`),
    enabled,
    staleTime: 30 * 60_000,
  });
}

export function useMacroFx(enabled: boolean = true) {
  return useQuery<FxRate[]>({
    queryKey: ["macro", "fx"],
    queryFn: () => publicGet<FxRate[]>("/api/macro/fx"),
    enabled,
    staleTime: 30 * 60_000,
  });
}

export function usePolicyRate(enabled: boolean = true) {
  return useQuery<PolicyRate>({
    queryKey: ["macro", "policy-rate"],
    queryFn: () => publicGet<PolicyRate>("/api/macro/policy-rate"),
    enabled,
    staleTime: 60 * 60_000,
  });
}
