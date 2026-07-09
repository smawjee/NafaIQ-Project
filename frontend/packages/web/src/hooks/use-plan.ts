import { useAuth } from "@/hooks/use-auth";
import { useMutation } from "@tanstack/react-query";

type Plan = "Free" | "Pro" | "Premium";

const PLAN_LIMITS: Record<Plan, Record<string, number>> = {
  Free: { portfolios: 1, budgets: 3, goals: 2, price_alerts: 3 },
  Pro: { portfolios: 999, budgets: 999, goals: 999, price_alerts: 999 },
  Premium: { portfolios: 999, budgets: 999, goals: 999, price_alerts: 999 },
};

const PLAN_HIERARCHY: Plan[] = ["Free", "Pro", "Premium"];

export function usePlan() {
  const { profile, user } = useAuth();
  const plan: Plan = (profile?.plan as Plan) || "Free";

  const canAccess = (feature: keyof typeof PLAN_LIMITS.Free): boolean => {
    return true; // Feature gating is deferred — always return true for now
  };

  const getLimit = (feature: keyof typeof PLAN_LIMITS.Free): number => {
    return PLAN_LIMITS[plan]?.[feature] ?? 999;
  };

  const planIndex = PLAN_HIERARCHY.indexOf(plan);

  return { plan, canAccess, getLimit, planIndex };
}

export function useUpgradePlan() {
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (newPlan: Plan) => {
      if (!user) throw new Error("Not authenticated");
      throw new Error(`${newPlan} upgrades require the server-side billing/admin flow.`);
    },
  });
}
