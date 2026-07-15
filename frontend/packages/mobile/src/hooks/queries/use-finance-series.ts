// Finance chart-series hooks — ported verbatim from the web app's
// use-finance-series.ts (endpoints: /api/finance/income-expense and
// /api/finance/spending-by-category).
import { useQuery } from "@tanstack/react-query";

import { userGet } from "@/lib/api";

export interface IncomeExpensePoint {
  month: string;
  income: number;
  expense: number;
}

export interface IncomeExpenseResponse {
  months: number;
  series: IncomeExpensePoint[];
}

export interface SpendingCategory {
  category: string;
  amount: number;
  pct: number;
}

export interface SpendingByCategoryResponse {
  days: number;
  total: number;
  categories: SpendingCategory[];
}

export function useIncomeExpenseSeries(months: number = 6, enabled: boolean = true) {
  return useQuery<IncomeExpenseResponse>({
    queryKey: ["finance", "income-expense", months],
    queryFn: () => userGet<IncomeExpenseResponse>(`/api/finance/income-expense?months=${months}`),
    enabled,
    staleTime: 60_000,
  });
}

export function useSpendingByCategory(days: number = 30, enabled: boolean = true) {
  return useQuery<SpendingByCategoryResponse>({
    queryKey: ["finance", "spending-by-category", days],
    queryFn: () =>
      userGet<SpendingByCategoryResponse>(`/api/finance/spending-by-category?days=${days}`),
    enabled,
    staleTime: 60_000,
  });
}
