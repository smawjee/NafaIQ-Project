import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userDelete, userGet, userPatch, userPost } from "@/lib/psx/client";

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
