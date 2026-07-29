// Plan features table (frontend mirror of public.plan_features in DB).
// Keep this in sync with backend/src/app/services/permissions.py and
// backend/database/migrations/20260711000000_role_and_plans.sql.

export type Plan = "Free" | "Pro" | "Premium";

export interface PlanFeatures {
  plan: Plan;
  rank: number;
  max_watchlist: number;
  max_price_alerts: number;
  max_portfolios: number;
  max_holdings_per_portfolio: number;
  max_budgets: number;
  max_bills: number;
  max_goals: number;
  max_finance_history_days: number;
  ai_tutor_daily_limit: number | null;
  ai_reports_per_period: number | null;
  ai_reports_period: "day" | "week" | "month" | null;
  has_email_alerts: boolean;
  has_push_alerts: boolean;
  has_export: boolean;
  has_multi_currency: boolean;
  has_realtime_psx: boolean;
  has_screener_full: boolean;
  has_webhook_integration: boolean;
  has_api_access: boolean;
  description: string | null;
}

export const PLAN_FEATURES: Record<Plan, PlanFeatures> = {
  Free: {
    plan: "Free",
    rank: 0,
    max_watchlist: 10,
    max_price_alerts: 5,
    max_portfolios: 1,
    max_holdings_per_portfolio: 20,
    max_budgets: 5,
    max_bills: 5,
    max_goals: 3,
    max_finance_history_days: 30,
    ai_tutor_daily_limit: 10,
    ai_reports_per_period: 3,
    ai_reports_period: "month",
    has_email_alerts: false,
    has_push_alerts: false,
    has_export: false,
    has_multi_currency: false,
    has_realtime_psx: false,
    has_screener_full: false,
    has_webhook_integration: false,
    has_api_access: false,
    description: "Free tier with delayed data",
  },
  Pro: {
    plan: "Pro",
    rank: 1,
    max_watchlist: 50,
    max_price_alerts: 50,
    max_portfolios: 5,
    max_holdings_per_portfolio: 100,
    max_budgets: 20,
    max_bills: 30,
    max_goals: 10,
    max_finance_history_days: 365,
    ai_tutor_daily_limit: null,
    ai_reports_per_period: 1,
    ai_reports_period: "week",
    has_email_alerts: true,
    has_push_alerts: true,
    has_export: true,
    has_multi_currency: true,
    has_realtime_psx: true,
    has_screener_full: true,
    has_webhook_integration: false,
    has_api_access: false,
    description: "Pro tier with real-time data",
  },
  Premium: {
    plan: "Premium",
    rank: 2,
    max_watchlist: 10000,
    max_price_alerts: 10000,
    max_portfolios: 1000,
    max_holdings_per_portfolio: 10000,
    max_budgets: 10000,
    max_bills: 10000,
    max_goals: 10000,
    max_finance_history_days: 36500,
    ai_tutor_daily_limit: null,
    ai_reports_per_period: null,
    ai_reports_period: null,
    has_email_alerts: true,
    has_push_alerts: true,
    has_export: true,
    has_multi_currency: true,
    has_realtime_psx: true,
    has_screener_full: true,
    has_webhook_integration: true,
    has_api_access: true,
    description: "Premium tier with all features",
  },
};

export const PLAN_RANK: Record<Plan, number> = { Free: 0, Pro: 1, Premium: 2 };

export function normalizePlan(plan: string | null | undefined): Plan {
  if (!plan) return "Free";
  // Case-insensitive, matching backend permissions.py normalize_plan(), which
  // does `plan.strip().title()`. Comparing exactly used to send a plan stored
  // as "pro" to Free, gating a paying user down while the backend still
  // authorised them as Pro (KAN-1). Plan names are single words, so
  // first-upper/rest-lower is equivalent to Python's .title().
  const p = plan.trim();
  const titled = p.charAt(0).toUpperCase() + p.slice(1).toLowerCase();
  if (titled === "Free" || titled === "Pro" || titled === "Premium") return titled;
  return "Free";
}

export function hasPlan(userPlan: string | null | undefined, required: Plan): boolean {
  return PLAN_RANK[normalizePlan(userPlan)] >= PLAN_RANK[required];
}

export function getPlanFeatures(plan: string | null | undefined): PlanFeatures {
  return PLAN_FEATURES[normalizePlan(plan)];
}
