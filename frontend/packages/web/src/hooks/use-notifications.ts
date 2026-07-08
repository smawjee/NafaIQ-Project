import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";
import { userGet, userPatch } from "@/lib/psx/client";

export interface InAppNotification {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationPrefs {
  email_alerts: boolean;
  push_alerts: boolean;
  in_app_alerts: boolean;
}

export function useNotifications() {
  const { user } = useAuth();
  const qc = useQueryClient();

  const query = useQuery<InAppNotification[]>({
    queryKey: ["notifications", user?.id],
    queryFn: () => userGet<InAppNotification[]>("/api/notifications/list"),
    enabled: !!user,
    staleTime: 30_000,
  });

  // Realtime subscription
  useEffect(() => {
    if (!user) return;
    const channel = supabase
      .channel("user-notifications")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "in_app_notifications", filter: `user_id=eq.${user.id}` },
        () => {
          qc.invalidateQueries({ queryKey: ["notifications"] });
        }
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [user, qc]);

  return query;
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => userPatch<{ id: number; read: boolean }>(`/api/notifications/${id}/read`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useNotificationPrefs() {
  const { user } = useAuth();
  return useQuery<NotificationPrefs>({
    queryKey: ["notification_prefs", user?.id],
    queryFn: () => userGet<NotificationPrefs>("/api/notifications/preferences"),
    enabled: !!user,
    staleTime: 60_000,
  });
}

export function useUpdateNotificationPrefs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (prefs: Partial<NotificationPrefs>) =>
      userPatch<{ ok: boolean }>("/api/notifications/preferences", prefs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notification_prefs"] });
    },
  });
}
