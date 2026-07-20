// Mutual funds (MUFAP) — public GET /api/funds, /api/funds/{code}, /nav.
// Backend returns raw psx_mutual_funds rows (select *); fields are typed
// best-effort with an index signature for columns the UI doesn't name.
import { useQuery } from "@tanstack/react-query";

import { publicGet } from "@/lib/api";

export interface Fund {
  fund_code: string;
  name: string;
  category: string | null;
  nav: number | null;
  amc?: string | null;
  fund_type?: string | null;
  [key: string]: unknown;
}

export interface FundNavPoint {
  date: string;
  nav: number;
  [key: string]: unknown;
}

export function useFunds(category?: string, enabled: boolean = true) {
  const qs = category ? `?category=${encodeURIComponent(category)}` : "";
  return useQuery<Fund[]>({
    queryKey: ["funds", category ?? "all"],
    queryFn: () => publicGet<Fund[]>(`/api/funds${qs}`),
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function useFund(code: string | undefined) {
  return useQuery<Fund>({
    queryKey: ["funds", "detail", code],
    queryFn: () => publicGet<Fund>(`/api/funds/${code}`),
    enabled: !!code,
    staleTime: 10 * 60_000,
  });
}

export function useFundNav(code: string | undefined) {
  return useQuery<FundNavPoint[]>({
    queryKey: ["funds", "nav", code],
    queryFn: () => publicGet<FundNavPoint[]>(`/api/funds/${code}/nav`),
    enabled: !!code,
    staleTime: 10 * 60_000,
  });
}
