import { createSelector } from "@reduxjs/toolkit";
import type { RootState } from "../index";

export const selectTransactions = (state: RootState) => state.finance.transactions;
export const selectBills = (state: RootState) => state.finance.bills;
export const selectBudgets = (state: RootState) => state.finance.budgets;
export const selectGoals = (state: RootState) => state.finance.goals;

export const selectTotalIncome = createSelector(selectTransactions, (txns) =>
  txns.filter((t) => t.amount > 0).reduce((s, t) => s + t.amount, 0),
);

export const selectTotalExpenses = createSelector(selectTransactions, (txns) =>
  txns.filter((t) => t.amount < 0).reduce((s, t) => s + Math.abs(t.amount), 0),
);

export const selectGoalsSummary = createSelector(selectGoals, (goals) => ({
  total: goals.length,
  totalSaved: goals.reduce((s, g) => s + g.saved, 0),
  totalTarget: goals.reduce((s, g) => s + g.target, 0),
}));

export const selectFinanceSummary = createSelector(
  selectTotalIncome,
  selectTotalExpenses,
  (income, expenses) => {
    const savings = income - expenses;
    return {
      income,
      expenses,
      savings,
      savingsRate: income > 0 ? (savings / income) * 100 : 0,
    };
  },
);

const SPENDING_PALETTE = ["#00d4aa", "#3b82f6", "#f59e0b", "#8b5cf6", "#6b7280"];

export const selectSpendingBreakdown = createSelector(selectTransactions, (txns) => {
  const totals = new Map<string, number>();
  for (const t of txns) {
    if (t.amount >= 0) continue;
    totals.set(t.category, (totals.get(t.category) ?? 0) + Math.abs(t.amount));
  }
  const sorted = Array.from(totals.entries()).sort((a, b) => b[1] - a[1]);
  const total = sorted.reduce((s, [, v]) => s + v, 0);
  const top = sorted.slice(0, 4);
  const otherAmount = sorted.slice(4).reduce((s, [, v]) => s + v, 0);
  if (otherAmount > 0) top.push(["Other", otherAmount]);
  return {
    total,
    categories: top.map(([name, amount], i) => ({
      name,
      amount,
      value: total > 0 ? Math.round((amount / total) * 100) : 0,
      color: SPENDING_PALETTE[i % SPENDING_PALETTE.length],
    })),
  };
});
