// Financials — public GET /api/financials/{symbol}/annual and /quarterly.
// Thin HTTP layer over the psx_financials_annual / psx_financials_quarterly
// tables (see backend/src/app/api/financials_extended.py). The backend returns
// raw rows, so the row shapes are typed best-effort with an index signature.
import { useQuery } from "@tanstack/react-query";

import { publicGet } from "@/lib/api";

/** One `psx_financials_annual` row (newest year first from the API). */
export interface AnnualFinancial {
  symbol: string;
  year: number;
  sales: number | null;
  cogs: number | null;
  gp: number | null;
  op_income: number | null;
  net_income: number | null;
  eps: number | null;
  total_assets: number | null;
  total_equity: number | null;
  total_debt: number | null;
  current_assets: number | null;
  current_liabilities: number | null;
  gpm: number | null;
  npm: number | null;
  roe: number | null;
  roa: number | null;
  refreshed_at?: string | null;
  [key: string]: unknown;
}

/** One `psx_financials_quarterly` row (most recent period first). */
export interface QuarterlyFinancial {
  symbol: string;
  period: string;
  end_date: string | null;
  sales: number | null;
  net_income: number | null;
  eps: number | null;
  refreshed_at?: string | null;
  [key: string]: unknown;
}

export function useAnnualFinancials(symbol: string | undefined, limit = 10) {
  return useQuery<AnnualFinancial[]>({
    queryKey: ["financials", "annual", symbol, limit],
    queryFn: () => publicGet<AnnualFinancial[]>(`/api/financials/${symbol}/annual?limit=${limit}`),
    enabled: !!symbol,
    staleTime: 24 * 60 * 60 * 1000, // weekly refresh upstream — once-per-day is fine
  });
}

export function useQuarterlyFinancials(symbol: string | undefined, limit = 20) {
  return useQuery<QuarterlyFinancial[]>({
    queryKey: ["financials", "quarterly", symbol, limit],
    queryFn: () =>
      publicGet<QuarterlyFinancial[]>(`/api/financials/${symbol}/quarterly?limit=${limit}`),
    enabled: !!symbol,
    staleTime: 24 * 60 * 60 * 1000,
  });
}
