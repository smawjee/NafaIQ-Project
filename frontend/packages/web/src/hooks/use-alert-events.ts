import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userDelete, userGet, userPatch, userPost } from "@/lib/psx/client";
import type { PriceCondition } from "@/features/alerts/alerts.data";

export type AlertEventType = "stock_price" | "bill" | "budget" | "goal" | "system";

export interface AlertEvent {
  id: number;
  user_id: string;
  alert_id: number | null;
  alert_type: AlertEventType;
  symbol: string | null;
  title: string;
  body: string;
  payload: Record<string, unknown>;
  channel: "in_app" | "email" | "push";
  delivered_at: string | null;
  read_at: string | null;
  created_at: string;
}

export interface AppAlert {
  id: number;
  user_id: string;
  type: AlertEventType;
  title: string;
  meta: Record<string, unknown>;
  enabled: boolean;
  triggered_at: string | null;
  created_at: string;
}

export interface PriceAlert {
  id: number;
  user_id: string;
  symbol: string;
  condition: PriceCondition;
  price: number;
  enabled: boolean;
  triggered_at: string | null;
  last_triggered_at: string | null;
  one_time: boolean;
  notify_push: boolean;
  notify_email: boolean;
  notes: string | null;
  created_at: string;
}

export function useAlertEvents(limit: number = 50, enabled: boolean = true) {
  return useQuery<AlertEvent[]>({
    queryKey: ["alerts", "events", limit],
    queryFn: () => userGet<AlertEvent[]>(`/api/alerts/events?limit=${limit}`),
    enabled,
    staleTime: 30_000,
  });
}

export function useMarkAlertEventRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      userPatch<{ id: number; read_at_set: boolean }>(`/api/alerts/events/${id}/read`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts", "events"] });
    },
  });
}

export function useAllAlerts(enabled: boolean = true) {
  return useQuery<AppAlert[]>({
    queryKey: ["alerts", "list"],
    queryFn: () => userGet<AppAlert[]>("/api/alerts"),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      type: AlertEventType;
      title: string;
      meta?: Record<string, unknown>;
      enabled?: boolean;
    }) => userPost<AppAlert>("/api/alerts", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useToggleAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      userPatch<{ id: number; enabled: boolean }>(`/api/alerts/${id}`, { enabled }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userDelete<{ deleted: number }>(`/api/alerts/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function usePriceAlerts(enabled: boolean = true) {
  return useQuery<PriceAlert[]>({
    queryKey: ["alerts", "price"],
    queryFn: () => userGet<PriceAlert[]>("/api/alerts/price"),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreatePriceAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      symbol: string;
      condition: PriceCondition;
      price: number;
      one_time?: boolean;
      notify_push?: boolean;
      notify_email?: boolean;
      notes?: string;
    }) => userPost<PriceAlert>("/api/alerts/price", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useEvaluateAlerts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      userPost<{
        price_alerts: number;
        bill_reminders: number;
        budget_alerts: number;
        goal_alerts: number;
      }>("/api/alerts/evaluate", {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
