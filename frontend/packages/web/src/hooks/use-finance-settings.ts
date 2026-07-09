import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userGet, userPatch } from "@/lib/psx/client";

export interface FinanceSettings {
  monthly_income: number;
  currency: string;
  language: string;
  plan: string;
}

export interface NotificationPrefs {
  email_alerts: boolean;
  push_alerts: boolean;
  in_app_alerts: boolean;
}

export function useFinanceSettings(enabled: boolean = true) {
  return useQuery<FinanceSettings>({
    queryKey: ["finance", "settings"],
    queryFn: () => userGet<FinanceSettings>("/api/finance/settings"),
    enabled,
    staleTime: 60_000,
  });
}

export function useUpdateFinanceSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<FinanceSettings>) =>
      userPatch<{ ok: boolean }>("/api/finance/settings", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["finance", "settings"] });
    },
  });
}

export function useNotificationPrefs(enabled: boolean = true) {
  return useQuery<NotificationPrefs>({
    queryKey: ["notification_prefs", enabled],
    queryFn: () => userGet<NotificationPrefs>("/api/notifications/preferences"),
    enabled,
    staleTime: 60_000,
  });
}

export function useUpdateNotificationPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<NotificationPrefs>) =>
      userPatch<{ ok: boolean }>("/api/notifications/preferences", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notification_prefs"] });
    },
  });
}
