import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userGet, userPost, userPatch, userDelete } from "@/lib/psx/client";

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
    mutationFn: ({
      id,
      ...data
    }: {
      id: number;
      spent?: number;
      limit_amount?: number;
      tip?: string;
    }) => userPatch<FinanceBudget>(`/api/finance/budgets/${id}`, data),
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
