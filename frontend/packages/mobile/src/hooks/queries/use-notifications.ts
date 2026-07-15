// In-app notifications — ported from the web app's src/hooks/use-notifications.ts
// (GET /api/notifications/list + PATCH /api/notifications/:id/read). The web
// hook also subscribes to Supabase realtime inserts; mobile polls instead
// (refetchInterval) to keep the bell badge fresh without a per-mount channel.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/use-auth";
import { userGet, userPatch } from "@/lib/api";

export interface InAppNotification {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  read: boolean;
  created_at: string;
}

export function useNotifications(enabled?: boolean) {
  const { user } = useAuth();
  const isEnabled = enabled ?? !!user;
  return useQuery<InAppNotification[]>({
    queryKey: ["notifications", user?.id],
    queryFn: () => userGet<InAppNotification[]>("/api/notifications/list"),
    enabled: isEnabled,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      userPatch<{ id: number; read: boolean }>(`/api/notifications/${id}/read`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
