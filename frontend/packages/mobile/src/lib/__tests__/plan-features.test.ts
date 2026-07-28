/**
 * Mobile plan gating. Mirrors the web suite at
 * frontend/packages/web/src/lib/__tests__/plan-features.test.ts — the two files
 * are byte-identical logic, so they must be held to the same contract.
 */
import {
  getPlanFeatures,
  hasPlan,
  normalizePlan,
  PLAN_FEATURES,
  PLAN_RANK,
  type Plan,
} from "@/lib/plan-features";

const PLANS: Plan[] = ["Free", "Pro", "Premium"];

describe("normalizePlan", () => {
  it("passes the three canonical plan names through untouched", () => {
    for (const plan of PLANS) expect(normalizePlan(plan)).toBe(plan);
  });

  it("falls back to Free for null, undefined and empty input", () => {
    expect(normalizePlan(null)).toBe("Free");
    expect(normalizePlan(undefined)).toBe("Free");
    expect(normalizePlan("")).toBe("Free");
  });

  it("trims surrounding whitespace", () => {
    expect(normalizePlan("  Pro  ")).toBe("Pro");
  });

  it("falls back to Free for an unrecognised plan name", () => {
    expect(normalizePlan("Enterprise")).toBe("Free");
  });

  // See KAN-1. Documents today's behaviour; not an endorsement of it.
  it("is case-SENSITIVE, unlike the backend it claims to mirror", () => {
    expect(normalizePlan("pro")).toBe("Free");
    expect(normalizePlan("PREMIUM")).toBe("Free");
  });
});

/**
 * KAN-1: backend permissions.py normalize_plan() does `.strip().title()`, so
 * "pro" becomes "Pro". Mobile (and web) compare exactly, so "pro" becomes
 * "Free" and a paying user is gated down while the backend still authorises
 * them as Pro. Un-skip this when the fix lands.
 */
describe("plan normalisation parity with the backend", () => {
  it.skip("should title-case like backend permissions.py normalize_plan()", () => {
    expect(normalizePlan("pro")).toBe("Pro");
    expect(normalizePlan("PREMIUM")).toBe("Premium");
  });
});

describe("hasPlan", () => {
  it("grants a tier to itself and to everything below it", () => {
    expect(hasPlan("Premium", "Pro")).toBe(true);
    expect(hasPlan("Pro", "Pro")).toBe(true);
    expect(hasPlan("Pro", "Free")).toBe(true);
  });

  it("denies a tier above the user's own", () => {
    expect(hasPlan("Free", "Pro")).toBe(false);
    expect(hasPlan("Pro", "Premium")).toBe(false);
  });

  it("treats a missing plan as Free", () => {
    expect(hasPlan(null, "Free")).toBe(true);
    expect(hasPlan(null, "Pro")).toBe(false);
  });
});

describe("getPlanFeatures", () => {
  it("returns the matching feature row", () => {
    expect(getPlanFeatures("Pro")).toBe(PLAN_FEATURES.Pro);
  });

  it("returns the Free row for unknown input", () => {
    expect(getPlanFeatures("nope")).toBe(PLAN_FEATURES.Free);
  });
});

describe("PLAN_FEATURES table invariants", () => {
  it("keeps rank consistent with PLAN_RANK", () => {
    for (const plan of PLANS) expect(PLAN_FEATURES[plan].rank).toBe(PLAN_RANK[plan]);
  });

  it("never decreases a numeric limit as the tier goes up", () => {
    const numericKeys = [
      "max_watchlist",
      "max_price_alerts",
      "max_portfolios",
      "max_holdings_per_portfolio",
      "max_budgets",
      "max_bills",
      "max_goals",
      "max_finance_history_days",
    ] as const;

    for (const key of numericKeys) {
      expect(PLAN_FEATURES.Pro[key]).toBeGreaterThanOrEqual(PLAN_FEATURES.Free[key]);
      expect(PLAN_FEATURES.Premium[key]).toBeGreaterThanOrEqual(PLAN_FEATURES.Pro[key]);
    }
  });

  it("never revokes a boolean capability as the tier goes up", () => {
    const boolKeys = [
      "has_email_alerts",
      "has_push_alerts",
      "has_export",
      "has_multi_currency",
      "has_realtime_psx",
      "has_screener_full",
      "has_webhook_integration",
      "has_api_access",
    ] as const;

    for (const key of boolKeys) {
      if (PLAN_FEATURES.Free[key]) expect(PLAN_FEATURES.Pro[key]).toBe(true);
      if (PLAN_FEATURES.Pro[key]) expect(PLAN_FEATURES.Premium[key]).toBe(true);
    }
  });

  it("stays byte-for-byte in step with the web table", () => {
    // Both platforms mirror public.plan_features. If they drift, one platform
    // silently gates differently from the other for the same account.
    expect(PLAN_FEATURES.Free.max_watchlist).toBe(10);
    expect(PLAN_FEATURES.Pro.max_watchlist).toBe(50);
    expect(PLAN_FEATURES.Premium.max_watchlist).toBe(10000);
    expect(PLAN_FEATURES.Free.ai_tutor_daily_limit).toBe(10);
    expect(PLAN_FEATURES.Pro.ai_tutor_daily_limit).toBeNull();
  });
});
