import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { TRANSACTIONS, BILLS, BUDGETS, GOALS } from "@/lib/finance/data";
import type { FinanceState, Txn, Bill, Budget, Goal } from "./types";

function dayLabel() {
  const d = new Date();
  return d.toLocaleString("en-US", { month: "long", day: "numeric" });
}

const initialState: FinanceState = {
  transactions: TRANSACTIONS.map((t) => ({ ...t })),
  bills: BILLS.map((b) => ({ ...b })),
  budgets: BUDGETS.map((b) => ({ ...b })),
  goals: GOALS.map((g) => ({ ...g })),
};

const financeSlice = createSlice({
  name: "finance",
  initialState,
  reducers: {
    addTransaction(state, action: PayloadAction<Omit<Txn, "date"> & { date?: string }>) {
      state.transactions.unshift({
        ...action.payload,
        date: action.payload.date || dayLabel(),
      });
    },
    removeTransaction(state, action: PayloadAction<number>) {
      state.transactions.splice(action.payload, 1);
    },
    editTransaction(state, action: PayloadAction<{ index: number; updates: Partial<Txn> }>) {
      const txn = state.transactions[action.payload.index];
      if (txn) Object.assign(txn, action.payload.updates);
    },
    addBill(state, action: PayloadAction<Bill>) {
      state.bills.push(action.payload);
    },
    removeBill(state, action: PayloadAction<number>) {
      state.bills.splice(action.payload, 1);
    },
    markBillPaid(state, action: PayloadAction<string>) {
      const bill = state.bills.find((b) => b.name === action.payload);
      if (bill) {
        state.transactions.unshift({
          date: dayLabel(),
          merchant: bill.name,
          category: "Utilities",
          account: "HBL Current",
          amount: -bill.amount,
        });
        state.bills = state.bills.filter((b) => b.name !== action.payload);
      }
    },
    addGoal(state, action: PayloadAction<Goal>) {
      state.goals.push(action.payload);
    },
    contributeToGoal(state, action: PayloadAction<{ name: string; amount: number }>) {
      const { name, amount } = action.payload;
      const goal = state.goals.find((g) => g.name === name);
      if (goal) {
        goal.saved = Math.min(goal.saved + amount, goal.target);
        state.transactions.unshift({
          date: dayLabel(),
          merchant: `${name} Transfer`,
          category: "Savings",
          account: "Meezan Savings",
          amount: -amount,
        });
      }
    },
    removeGoal(state, action: PayloadAction<string>) {
      state.goals = state.goals.filter((g) => g.name !== action.payload);
    },
    addBudget(state, action: PayloadAction<Budget>) {
      state.budgets.push(action.payload);
    },
    updateBudget(state, action: PayloadAction<{ category: string; updates: Partial<Budget> }>) {
      const budget = state.budgets.find((b) => b.category === action.payload.category);
      if (budget) {
        Object.assign(budget, action.payload.updates);
      }
    },
    removeBudget(state, action: PayloadAction<number>) {
      state.budgets.splice(action.payload, 1);
    },
    resetFinance(state) {
      state.transactions = TRANSACTIONS.map((t) => ({ ...t }));
      state.bills = BILLS.map((b) => ({ ...b }));
      state.budgets = BUDGETS.map((b) => ({ ...b }));
      state.goals = GOALS.map((g) => ({ ...g }));
    },
  },
});

export const {
  addTransaction,
  removeTransaction,
  editTransaction,
  addBill,
  removeBill,
  markBillPaid,
  addGoal,
  contributeToGoal,
  removeGoal,
  addBudget,
  updateBudget,
  removeBudget,
  resetFinance,
} = financeSlice.actions;
export default financeSlice.reducer;
