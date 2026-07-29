// Notification channel preferences. Mirrors web hooks/use-finance-settings.ts
// (useNotificationPrefs / useUpdateNotificationPrefs) — same endpoints, query
// keys, and shape. Toggling from either platform serves both since the prefs
// live on the user's profile server-side.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userGet, userPatch } from "@/lib/api";

export interface NotificationPrefs {
  email_alerts: boolean;
  email_activity: boolean;
  push_alerts: boolean;
  in_app_alerts: boolean;
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
