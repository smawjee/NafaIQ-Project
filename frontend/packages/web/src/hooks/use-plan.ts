import { useAuth } from "@/hooks/use-auth";
import { getPlanFeatures, normalizePlan, PLAN_RANK, type Plan, type PlanFeatures } from "@/lib/plan-features";
import { useMutation } from "@tanstack/react-query";

type LimitFeature = "portfolios" | "budgets" | "goals" | "price_alerts";

const LIMIT_KEYS: Record<
  LimitFeature,
  keyof Pick<PlanFeatures, "max_portfolios" | "max_budgets" | "max_goals" | "max_price_alerts">
> = {
  portfolios: "max_portfolios",
  budgets: "max_budgets",
  goals: "max_goals",
  price_alerts: "max_price_alerts",
};

export function usePlan() {
  const { profile } = useAuth();
  const plan = normalizePlan(profile?.plan);
  const features = getPlanFeatures(plan);

  const getLimit = (feature: LimitFeature): number => {
    return Number(features[LIMIT_KEYS[feature]] ?? 0);
  };

  const canAccess = (feature: LimitFeature): boolean => {
    return getLimit(feature) > 0;
  };

  const planIndex = PLAN_RANK[plan];

  return { plan, features, canAccess, getLimit, planIndex };
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
