import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userGet, userPatch, userPost } from "@/lib/psx/client";

export interface ZakatSettings {
  user_id: string;
  method: "standard_2_5" | "custom_rate" | "manual_only";
  custom_rate_pct: number | null;
  nisab_source: "gold" | "silver" | "cash" | "manual";
  nisab_value_pkr: number | null;
  include_cash: boolean;
  include_investments: boolean;
  include_receivables: boolean;
  notes: string | null;
  updated_at: string | null;
}

export interface ZakatRecord {
  id: number;
  user_id: string;
  islamic_year: string;
  method: string;
  nisab_value_pkr: number;
  total_assets_pkr: number;
  total_deductions_pkr: number;
  net_zakatable_pkr: number;
  rate_pct: number;
  zakat_due_pkr: number;
  breakdown: Record<string, unknown>;
  calculated_at: string;
  created_at: string;
}

export function useZakatSettings(enabled: boolean = true) {
  return useQuery<ZakatSettings>({
    queryKey: ["zakat", "settings"],
    queryFn: () => userGet<ZakatSettings>("/api/finance/zakat/settings"),
    enabled,
    staleTime: 60_000,
  });
}

export function useUpdateZakatSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (updates: Partial<ZakatSettings>) =>
      userPatch<ZakatSettings>("/api/finance/zakat/settings", updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["zakat", "settings"] });
    },
  });
}

export function useZakatHistory(limit: number = 20, enabled: boolean = true) {
  return useQuery<ZakatRecord[]>({
    queryKey: ["zakat", "history", limit],
    queryFn: () => userGet<ZakatRecord[]>(`/api/finance/zakat/history?limit=${limit}`),
    enabled,
    staleTime: 60_000,
  });
}

export function useCalculateZakat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      islamic_year: string;
      total_assets_pkr: number;
      total_deductions_pkr?: number;
      nisab_value_pkr: number;
      rate_pct?: number;
      method?: string;
      breakdown?: Record<string, unknown>;
      save?: boolean;
    }) => userPost<unknown>("/api/finance/zakat/calculate", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["zakat"] });
    },
  });
}
