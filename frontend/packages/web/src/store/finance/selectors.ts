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
