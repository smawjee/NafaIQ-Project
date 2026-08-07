import { useQuery } from "@tanstack/react-query";
import { userGet } from "@/lib/psx/client";

export interface FinanceSummary {
  month: string;
  income: number; // earned this month, from transactions (variable)
  fixed_income: number; // recurring monthly income (salary) from settings
  total_income: number; // recorded income, or fixed_income when none was recorded
  expenses: number;
  savings: number; // THIS MONTH only: total_income - expenses
  savings_rate: number;
  last_month_income: number;
  last_month_expense: number;
  last_month_savings: number;
  // Running balance. `savings` describes a single month in isolation; these
  // carry earlier months forward, so an unspent balance no longer disappears
  // on the 1st of each month.
  opening_balance: number; // what the user held on their opening-balance date
  carried_over: number; // opening_balance + the net of every earlier month
  available_balance: number; // carried_over + this month's savings
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
