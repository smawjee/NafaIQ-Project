// Finance settings (currency + monthly income). Mirrors web
// hooks/use-finance-settings.ts (useFinanceSettings / useUpdateFinanceSettings)
// — same endpoints, query keys, and shape. Persisted server-side so the values
// follow the user across web and mobile.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userGet, userPatch } from "@/lib/api";

export interface FinanceSettings {
  monthly_income: number;
  currency: string;
  language: string;
  plan: string;
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
