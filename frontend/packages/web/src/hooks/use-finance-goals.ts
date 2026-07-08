import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userGet, userPost, userPatch, userDelete } from "@/lib/psx/client";

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
    mutationFn: (data: { emoji?: string; name: string; target: number; saved?: number; color?: string; ai_tip?: string; target_date?: string }) =>
      userPost<FinanceGoal>("/api/finance/goals", data),
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
