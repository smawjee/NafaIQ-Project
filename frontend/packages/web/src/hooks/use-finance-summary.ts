import { useQuery } from "@tanstack/react-query";
import { userGet } from "@/lib/psx/client";

export interface FinanceSummary {
  month: string;
  income: number;
  expenses: number;
  savings: number;
  savings_rate: number;
  last_month_income: number;
  last_month_expense: number;
  last_month_savings: number;
}

export function useFinanceSummary(month?: string) {
  return useQuery<FinanceSummary>({
    queryKey: ["finance", "summary", month ?? "current"],
    queryFn: () => {
      const qs = month ? `?month=${month}` : "";
      return userGet<FinanceSummary>(`/api/finance/summary${qs}`);
    },
    staleTime: 60_000,
  });
}
