import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userDelete, userGet, userPatch, userPost } from "@/lib/psx/client";

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

export interface FinanceVocabulary {
  categories: string[];
  payment_methods: string[];
  transaction_types: Array<"expense" | "income" | string>;
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
export function useFinanceTransactions(enabled: boolean = true, limit: number = 100) {
  return useQuery<FinanceTransaction[]>({
    queryKey: ["finance", "transactions", limit],
    queryFn: () => userGet<FinanceTransaction[]>(`/api/finance/transactions?limit=${limit}`),
    enabled,
    staleTime: 30_000,
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
