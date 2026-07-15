// Alerts domain — React Query hooks over the FastAPI backend.
// Ported from web src/hooks/use-alert-events.ts (the current alerts path) with
// the endpoint wrappers from web src/lib/psx/client.ts inlined here on top of
// the mobile userGet/userPost/userPatch/userDelete (Supabase JWT) helpers.
// Backend source of truth: backend/src/app/api/alerts.py.
// Query keys and invalidation mirror the web hooks exactly.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userDelete, userGet, userPatch, userPost } from "@/lib/api";

/* --------------------------------- Types --------------------------------- */

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

export interface AppAlertCreate {
  type: AlertEventType;
  title: string;
  meta?: Record<string, unknown>;
  enabled?: boolean;
}

export interface EvaluateAlertsResult {
  price_alerts: number;
  bill_reminders: number;
  budget_alerts: number;
  goal_alerts: number;
}

/* ---------------------------- Endpoint wrappers --------------------------- */

export function fetchAllAlerts(): Promise<AppAlert[]> {
  return userGet<AppAlert[]>("/api/alerts");
}

export function createAlert(data: AppAlertCreate): Promise<AppAlert> {
  return userPost<AppAlert>("/api/alerts", data);
}

export function toggleAlert(id: number, enabled: boolean): Promise<{ id: number; enabled: boolean }> {
  return userPatch<{ id: number; enabled: boolean }>(`/api/alerts/${id}`, { enabled });
}

export function deleteAlert(id: number): Promise<{ deleted: number }> {
  return userDelete<{ deleted: number }>(`/api/alerts/${id}`);
}

export function fetchAlertEvents(limit = 50): Promise<AlertEvent[]> {
  return userGet<AlertEvent[]>(`/api/alerts/events?limit=${limit}`);
}

export function markAlertEventRead(id: number): Promise<{ id: number; read_at_set: boolean }> {
  return userPatch<{ id: number; read_at_set: boolean }>(`/api/alerts/events/${id}/read`, {});
}

export function evaluateAlerts(): Promise<EvaluateAlertsResult> {
  return userPost<EvaluateAlertsResult>("/api/alerts/evaluate", {});
}

/* ---------------------------------- Hooks --------------------------------- */

export function useAllAlerts(enabled: boolean = true) {
  return useQuery<AppAlert[]>({
    queryKey: ["alerts", "list"],
    queryFn: fetchAllAlerts,
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AppAlertCreate) => createAlert(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useToggleAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => toggleAlert(id, enabled),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteAlert(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useAlertEvents(limit: number = 50, enabled: boolean = true) {
  return useQuery<AlertEvent[]>({
    queryKey: ["alerts", "events", limit],
    queryFn: () => fetchAlertEvents(limit),
    enabled,
    staleTime: 30_000,
  });
}

export function useMarkAlertEventRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => markAlertEventRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts", "events"] });
    },
  });
}

export function useEvaluateAlerts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: evaluateAlerts,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
