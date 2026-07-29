import { useQuery } from "@tanstack/react-query";
import { userGet } from "@/lib/psx/client";

export interface FinanceSummary {
  month: string;
  income: number; // earned this month, from transactions (variable)
  fixed_income: number; // recurring monthly income (salary) from settings
  total_income: number; // income + fixed_income
  expenses: number;
  savings: number;
  savings_rate: number;
  last_month_income: number;
  last_month_expense: number;
  last_month_savings: number;
}

export function useFinanceSummary(month?: string, enabled: boolean = true) {
  return useQuery<FinanceSummary>({
    queryKey: ["finance", "summary", month ?? "current"],
    queryFn: () => {
      const qs = month ? `?month=${month}` : "";
      return userGet<FinanceSummary>(`/api/finance/summary${qs}`);
    },
    enabled,
    staleTime: 60_000,
  });
}
