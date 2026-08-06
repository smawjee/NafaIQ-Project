// Finance domain React Query hooks — ported from the web app's
// use-finance-transactions.ts / use-finance-budgets.ts / use-finance-goals.ts /
// use-finance-bills.ts / use-finance-summary.ts. Query keys, types and
// invalidation mirror the web hooks exactly; the backend contract lives in
// backend/src/app/api/finance.py + schemas/finance.py.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userDelete, userGet, userPatch, userPost } from "@/lib/api";

export type FinanceBulkEntity = "transactions" | "budgets" | "bills" | "goals";

export function useDeleteAllFinance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entity: FinanceBulkEntity) =>
      userDelete<{ deleted: number }>(`/api/finance/${entity}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

/* ------------------------------ Transactions ----------------------------- */

export interface FinanceTransaction {
  id: number;
  merchant: string;
  amount: number;
  currency: string;
  transaction_type: "income" | "expense" | string;
  category: string;
  transaction_date: string;
  source: string | null;
  note: string | null;
  created_at: string;
}

export interface FinanceTransactionInput {
  merchant: string;
  amount: number;
  transaction_type: "income" | "expense";
  category: string;
  transaction_date?: string | null;
  source?: string;
  note?: string | null;
}

/** Server vocabulary for the add/edit form: canonical categories plus the
 * user's own payment methods (seeded defaults + anything they added). */
export interface FinanceVocabulary {
  categories: string[];
  payment_methods: string[];
  transaction_types: ("expense" | "income" | string)[];
}

export interface FinancePaymentMethod {
  id: number;
  label: string;
  created_at: string;
}

export function useFinanceVocabulary(enabled: boolean = true) {
  return useQuery<FinanceVocabulary>({
    queryKey: ["finance", "vocabulary"],
    queryFn: () => userGet<FinanceVocabulary>("/api/finance/vocabulary"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useCreatePaymentMethod() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (label: string) =>
      userPost<FinancePaymentMethod>("/api/finance/payment-methods", { label }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance", "vocabulary"] });
    },
  });
}

export function useFinanceTransactions(enabled: boolean = true, limit: number = 100) {
  return useQuery<FinanceTransaction[]>({
    queryKey: ["finance", "transactions", limit],
    queryFn: () => userGet<FinanceTransaction[]>(`/api/finance/transactions?limit=${limit}`),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: FinanceTransactionInput) =>
      userPost<FinanceTransaction>("/api/finance/transactions", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export function useUpdateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<FinanceTransactionInput> & { id: number }) =>
      userPatch<FinanceTransaction>(`/api/finance/transactions/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export function useDeleteTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/finance/transactions/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

/* -------------------------------- Budgets -------------------------------- */

export interface FinanceBudget {
  id: number;
  user_id: string;
  category: string;
  spent: number;
  limit_amount: number;
  period: string;
  tip: string | null;
  created_at: string | null;
}

export function useFinanceBudgets(enabled: boolean = true) {
  return useQuery<FinanceBudget[]>({
    queryKey: ["finance", "budgets"],
    queryFn: () => userGet<FinanceBudget[]>("/api/finance/budgets"),
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      category: string;
      spent?: number;
      limit_amount: number;
      period?: string;
      tip?: string;
    }) => userPost<FinanceBudget>("/api/finance/budgets", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "budgets"] }),
  });
}

export function useUpdateBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; spent?: number; limit_amount?: number; tip?: string }) =>
      userPatch<FinanceBudget>(`/api/finance/budgets/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "budgets"] }),
  });
}

export function useDeleteBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/finance/budgets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "budgets"] }),
  });
}

/* --------------------------------- Goals --------------------------------- */

export interface FinanceGoal {
  id: number;
  user_id: string;
  emoji: string | null;
  name: string;
  target: number;
  saved: number;
  color: string | null;
  ai_tip: string | null;
  target_date: string | null;
  created_at: string | null;
}

export function useFinanceGoals(enabled: boolean = true) {
  return useQuery<FinanceGoal[]>({
    queryKey: ["finance", "goals"],
    queryFn: () => userGet<FinanceGoal[]>("/api/finance/goals"),
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      emoji?: string;
      name: string;
      target: number;
      saved?: number;
      color?: string;
      ai_tip?: string;
      target_date?: string;
    }) => userPost<FinanceGoal>("/api/finance/goals", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "goals"] }),
  });
}

export function useContributeGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      userPatch<FinanceGoal>(`/api/finance/goals/${id}/contribute`, { amount }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "goals"] }),
  });
}

export function useDeleteGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/finance/goals/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "goals"] }),
  });
}

/* --------------------------------- Bills --------------------------------- */

export type FinanceBillStatus = "UPCOMING" | "DUE SOON" | "PAID";

export interface FinanceBill {
  id: number;
  user_id: string;
  name: string;
  amount: number;
  currency: string;
  due_date: string | null;
  status: FinanceBillStatus;
  recurring: boolean;
  paid_at: string | null;
  created_at: string;
}

export interface FinanceBillInput {
  name: string;
  amount: number;
  due_date?: string | null;
  status?: FinanceBillStatus;
  recurring?: boolean;
}

export function useFinanceBills(enabled: boolean = true) {
  return useQuery<FinanceBill[]>({
    queryKey: ["finance", "bills"],
    queryFn: () => userGet<FinanceBill[]>("/api/finance/bills"),
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: FinanceBillInput) => userPost<FinanceBill>("/api/finance/bills", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export function useUpdateBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<FinanceBillInput> & { id: number }) =>
      userPatch<FinanceBill>(`/api/finance/bills/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export function useMarkBillPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userPatch<FinanceBill>(`/api/finance/bills/${id}/paid`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

export function useDeleteBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/finance/bills/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}

/* -------------------------------- Summary -------------------------------- */

export interface FinanceSummary {
  month: string;
  income: number; // earned this month from transactions (variable)
  fixed_income: number; // recurring monthly income (salary) from settings
  total_income: number; // income + fixed_income — the real monthly income
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
