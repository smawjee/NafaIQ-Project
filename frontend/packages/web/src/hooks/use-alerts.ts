import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";

export interface UserAlert {
  id: number;
  user_id: string;
  type: "stock_price" | "bill" | "budget" | "goal";
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
  condition: "above" | "below" | "cross_above" | "cross_below";
  price: number;
  enabled: boolean;
  triggered_at: string | null;
  created_at: string;
}

const userAlertsTable = "user_alerts" as const;
const priceAlertsTable = "price_alerts" as const;

export function useUserAlerts(enabled?: boolean) {
  const { user } = useAuth();
  return useQuery<UserAlert[]>({
    queryKey: ["user_alerts", user?.id],
    queryFn: async () => {
      if (!user) return [];
      const { data, error } = await supabase
        .from(userAlertsTable)
        .select("*")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return (data ?? []) as unknown as UserAlert[];
    },
    enabled: enabled ?? !!user,
    staleTime: 30_000,
  });
}

export function usePriceAlerts(enabled?: boolean) {
  const { user } = useAuth();
  return useQuery<PriceAlert[]>({
    queryKey: ["price_alerts", user?.id],
    queryFn: async () => {
      if (!user) return [];
      const { data, error } = await supabase
        .from(priceAlertsTable)
        .select("*")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return (data ?? []) as unknown as PriceAlert[];
    },
    enabled: enabled ?? !!user,
    staleTime: 30_000,
  });
}

export function useCreateUserAlert() {
  const { user } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (alert: {
      type: UserAlert["type"];
      title: string;
      meta?: Record<string, unknown>;
    }) => {
      if (!user) throw new Error("Not authenticated");
      const { data, error } = await supabase
        .from(userAlertsTable)
        .insert({ ...alert, user_id: user.id, meta: (alert.meta ?? {}) as never })
        .select()
        .single();
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user_alerts"] });
    },
  });
}

export function useToggleUserAlert() {
  const { user } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) => {
      if (!user) throw new Error("Not authenticated");
      const { error } = await supabase
        .from(userAlertsTable)
        .update({ enabled })
        .eq("id", id)
        .eq("user_id", user.id);
      if (error) throw error;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user_alerts"] });
    },
  });
}

export function useRemoveUserAlert() {
  const { user } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      if (!user) throw new Error("Not authenticated");
      const { error } = await supabase
        .from(userAlertsTable)
        .delete()
        .eq("id", id)
        .eq("user_id", user.id);
      if (error) throw error;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user_alerts"] });
    },
  });
}
