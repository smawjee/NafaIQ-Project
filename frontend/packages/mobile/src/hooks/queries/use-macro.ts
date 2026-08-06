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
  date: string | null;
  buy: number | null;
  sell: number | null;
  [key: string]: unknown;
}

export interface PolicyRate {
  series: string;
  date: string | null;
  value: number | null;
  [key: string]: unknown;
}

export interface MonetaryCurrency {
  code: string;
  name: string;
  per_usd: number;
  one_unit_in_pkr: number;
  one_pkr_in_unit: number;
}

export interface MonetaryMetal {
  code: "XAU" | "XAG";
  name: string;
  basis: string;
  usd_per_troy_oz: number;
  pkr_per_gram: number;
  pkr_per_10g: number;
  pkr_per_tola: number;
  source_name?: string | null;
  source_url?: string | null;
  cadence?: string | null;
  as_of?: string | null;
  city?: string | null;
}

export interface MonetarySnapshot {
  base: "USD";
  as_of: string | null;
  refreshed_at: string;
  expires_at: string;
  ttl_seconds: number;
  source: { name: string; url: string; cadence: string };
  metal_source: { name: string; url: string; cadence: string; as_of?: string | null; city?: string | null } | null;
  usd_pkr: number;
  rates: Record<string, number>;
  currencies: MonetaryCurrency[];
  metals: MonetaryMetal[];
  validation: {
    status: "cross_checked" | "single_source" | "review";
    max_deviation_pct: number;
    message: string;
    checked_against: { name: string; usd_pkr: number; deviation_pct: number; cadence: string; official: boolean }[];
  };
  warnings: string[];
  disclaimer: string;
  stale: boolean;
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

export function useMonetarySnapshot(enabled: boolean = true) {
  return useQuery<MonetarySnapshot>({
    queryKey: ["macro", "monetary"],
    queryFn: () => publicGet<MonetarySnapshot>("/api/macro/monetary"),
    enabled,
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  });
}
