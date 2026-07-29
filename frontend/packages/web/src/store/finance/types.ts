import type { Goal, Txn, Budget, Bill } from "@/lib/finance/data";

export type { Goal, Txn, Budget, Bill };

export interface FinanceState {
  transactions: Txn[];
  bills: Bill[];
  budgets: Budget[];
  goals: Goal[];
}
