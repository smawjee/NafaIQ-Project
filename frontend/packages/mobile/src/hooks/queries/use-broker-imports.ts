import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userGet, userPatch, userPost } from "@/lib/api";

export interface BrokerImport {
  id: number;
  broker_code: string;
  account_mask?: string | null;
  status: string;
  sanitized_subject: string;
  received_at: string;
  trade_date: string | null;
  total_quantity: number | null;
  total_net_amount: number | null;
  mapped_portfolio_id?: number | null;
  portfolio_name?: string | null;
  item_count?: number;
}

export interface BrokerAccount {
  id: number;
  broker_code: string;
  account_mask: string;
  mapped_portfolio_id: number | null;
  portfolio_name?: string | null;
  mode: "review" | "auto";
  pending_count: number;
}

export function useBrokerImports(status?: string, enabled = true) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return useQuery<{ items: BrokerImport[]; next_cursor: number | null }>({
    queryKey: ["broker_imports", status ?? "all"],
    queryFn: () => userGet(`/api/portfolio/broker-imports${qs}`),
    enabled,
    staleTime: 30_000,
  });
}

export function useBrokerAccounts(enabled = true) {
  return useQuery<BrokerAccount[]>({
    queryKey: ["broker_accounts"],
    queryFn: () => userGet("/api/portfolio/broker-accounts"),
    enabled,
    staleTime: 30_000,
  });
}

export function useApproveBrokerImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { importId: number; portfolioId: number; enableAuto: boolean }) =>
      userPost<BrokerImport>(`/api/portfolio/broker-imports/${data.importId}/approve`, {
        portfolio_id: data.portfolioId,
        enable_auto: data.enableAuto,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["broker_imports"] });
      qc.invalidateQueries({ queryKey: ["broker_accounts"] });
      qc.invalidateQueries({ queryKey: ["email_integration"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["finance"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useUpdateBrokerAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { accountId: number; mapped_portfolio_id?: number; mode?: "review" | "auto" }) =>
      userPatch<BrokerAccount>(`/api/portfolio/broker-accounts/${data.accountId}`, {
        mapped_portfolio_id: data.mapped_portfolio_id,
        mode: data.mode,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["broker_accounts"] }),
  });
}
