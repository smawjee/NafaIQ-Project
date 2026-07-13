// Plan hooks — mirrors web src/hooks/use-plan.ts.
// usePlan derives the current plan + feature limits from the auth profile;
// useUpgradePlan posts to the backend's sanctioned plan-change endpoint
// (POST /api/profile/plan) and refreshes the auth profile so
// plan/plan_selected_at propagate everywhere (same Supabase account as web).
import { useMutation } from "@tanstack/react-query";

import { useAuth } from "@/hooks/use-auth";
import { userPost } from "@/lib/api";
import {
  getPlanFeatures,
  normalizePlan,
  PLAN_RANK,
  type Plan,
  type PlanFeatures,
} from "@/lib/plan-features";

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
  const { user, refreshProfile } = useAuth();

  return useMutation({
    mutationFn: async (newPlan: Plan) => {
      if (!user) throw new Error("Not authenticated");
      // Sanctioned plan-change path (backend service connection); the DB
      // trigger still blocks direct client-side plan updates. When payments
      // land, Pro/Premium should route through checkout before this call.
      return userPost<{ plan: string; plan_selected_at: string }>("/api/profile/plan", {
        plan: newPlan,
      });
    },
    onSuccess: () => refreshProfile(),
  });
}
