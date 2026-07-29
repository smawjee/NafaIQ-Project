// Dedicated price alerts (price_alerts table) — GET/POST/DELETE /api/alerts/price.
// Distinct from the generic app-alert API (use-alerts.ts): these carry a
// condition + persisted notify_push/notify_email channels the backend honors.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userDelete, userGet, userPost } from "@/lib/api";

export type PriceAlertCondition = "above" | "below" | "cross_above" | "cross_below";

export interface PriceAlert {
  id: number;
  user_id: string;
  type: "stock_price";
  symbol: string;
  condition: PriceAlertCondition;
  price: number;
  one_time?: boolean;
  enabled: boolean;
  notes: string | null;
  created_at: string;
}

export interface PriceAlertCreate {
  symbol: string;
  condition: PriceAlertCondition;
  price: number;
  one_time?: boolean;
  notify_push?: boolean;
  notify_email?: boolean;
  notes?: string;
}

export function usePriceAlerts(enabled: boolean = true) {
  return useQuery<PriceAlert[]>({
    queryKey: ["price-alerts"],
    queryFn: () => userGet<PriceAlert[]>("/api/alerts/price"),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreatePriceAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PriceAlertCreate) => userPost<PriceAlert>("/api/alerts/price", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["price-alerts"] }),
  });
}

export function useDeletePriceAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/alerts/price/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["price-alerts"] }),
  });
}
