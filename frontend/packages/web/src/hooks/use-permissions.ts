import { useMemo } from "react";
import { useAuth } from "@/hooks/use-auth";
import { getPlanFeatures, hasPlan, normalizePlan, type Plan, type PlanFeatures } from "@/lib/plan-features";

export type Feature =
  | "realtime_psx"
  | "screener_full"
  | "multi_currency"
  | "export"
  | "email_alerts"
  | "push_alerts"
  | "webhook_integration"
  | "api_access"
  | "ai_tutor_unlimited"
  | "ai_reports"
  | "multi_portfolio"
  | "unlimited_holdings"
  | "unlimited_budgets"
  | "unlimited_bills"
  | "unlimited_goals"
  | "large_watchlist"
  | "large_price_alerts";

const FEATURE_TO_PLAN: Record<Feature, Plan> = {
  realtime_psx: "Pro",
  screener_full: "Pro",
  multi_currency: "Pro",
  export: "Pro",
  email_alerts: "Pro",
  push_alerts: "Pro",
  ai_tutor_unlimited: "Pro",
  ai_reports: "Pro",
  multi_portfolio: "Pro",
  unlimited_holdings: "Premium",
  unlimited_budgets: "Premium",
  unlimited_bills: "Premium",
  unlimited_goals: "Premium",
  large_watchlist: "Pro",
  large_price_alerts: "Pro",
  webhook_integration: "Premium",
  api_access: "Premium",
};

export function usePermissions() {
  const { profile, user } = useAuth();

  const plan: Plan = useMemo(() => normalizePlan(profile?.plan), [profile?.plan]);
  const features: PlanFeatures = useMemo(() => getPlanFeatures(plan), [plan]);

  const can = (feature: Feature): boolean => {
    if (!user) return false;
    const required = FEATURE_TO_PLAN[feature];
    return hasPlan(plan, required);
  };

  const upgradeHint = (feature: Feature): Plan | null => {
    if (can(feature)) return null;
    return FEATURE_TO_PLAN[feature];
  };

  const isAtOrAbove = (required: Plan): boolean => hasPlan(plan, required);

  return {
    plan,
    features,
    can,
    upgradeHint,
    isAtOrAbove,
  };
}
