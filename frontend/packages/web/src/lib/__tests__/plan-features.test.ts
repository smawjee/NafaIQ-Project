import { describe, expect, it } from "vitest";

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
    expect(normalizePlan("\tPremium\n")).toBe("Premium");
  });

  it("falls back to Free for an unrecognised plan name", () => {
    expect(normalizePlan("Enterprise")).toBe("Free");
    expect(normalizePlan("trial")).toBe("Free");
  });

  it("is case-insensitive, matching the backend (KAN-1)", () => {
    expect(normalizePlan("pro")).toBe("Pro");
    expect(normalizePlan("PRO")).toBe("Pro");
    expect(normalizePlan("premium")).toBe("Premium");
    expect(normalizePlan("PREMIUM")).toBe("Premium");
    expect(normalizePlan("pReMiUm")).toBe("Premium");
    expect(normalizePlan("  free  ")).toBe("Free");
  });
});

/**
 * Parity with backend/src/app/services/permissions.py normalize_plan(), which
 * does `plan.strip().title()`.
 *
 * Before KAN-1 was fixed, both frontends compared exactly, so a `profiles.plan`
 * of "pro" resolved to Free and gated a paying user down while the backend
 * still authorised them as Pro. The identical suite in
 * frontend/packages/mobile/src/lib/__tests__/plan-features.test.ts holds mobile
 * to the same contract.
 */
describe("plan normalisation parity with the backend", () => {
  it("title-cases like backend permissions.py normalize_plan()", () => {
    expect(normalizePlan("pro")).toBe("Pro");
    expect(normalizePlan("PREMIUM")).toBe("Premium");
    expect(normalizePlan("  free  ")).toBe("Free");
  });

  it("still rejects a value that is not a plan, whatever its casing", () => {
    expect(normalizePlan("enterprise")).toBe("Free");
    expect(normalizePlan("ENTERPRISE")).toBe("Free");
    expect(normalizePlan("prooo")).toBe("Free");
  });

  it("gates on the normalised value, so a lower-case Pro gets Pro limits", () => {
    expect(hasPlan("pro", "Pro")).toBe(true);
    expect(hasPlan("premium", "Pro")).toBe(true);
    expect(getPlanFeatures("pro").max_watchlist).toBe(PLAN_FEATURES.Pro.max_watchlist);
  });
});

describe("hasPlan", () => {
  it("grants a tier to itself and to everything below it", () => {
    expect(hasPlan("Premium", "Free")).toBe(true);
    expect(hasPlan("Premium", "Pro")).toBe(true);
    expect(hasPlan("Premium", "Premium")).toBe(true);
    expect(hasPlan("Pro", "Free")).toBe(true);
    expect(hasPlan("Pro", "Pro")).toBe(true);
    expect(hasPlan("Free", "Free")).toBe(true);
  });

  it("denies a tier above the user's own", () => {
    expect(hasPlan("Free", "Pro")).toBe(false);
    expect(hasPlan("Free", "Premium")).toBe(false);
    expect(hasPlan("Pro", "Premium")).toBe(false);
  });

  it("treats an unknown or missing plan as Free", () => {
    expect(hasPlan(null, "Free")).toBe(true);
    expect(hasPlan(null, "Pro")).toBe(false);
    expect(hasPlan("Enterprise", "Pro")).toBe(false);
  });
});

describe("getPlanFeatures", () => {
  it("returns the matching feature row", () => {
    expect(getPlanFeatures("Pro")).toBe(PLAN_FEATURES.Pro);
    expect(getPlanFeatures("Premium").plan).toBe("Premium");
  });

  it("returns the Free row for unknown or missing input", () => {
    expect(getPlanFeatures(undefined)).toBe(PLAN_FEATURES.Free);
    expect(getPlanFeatures("nope")).toBe(PLAN_FEATURES.Free);
  });
});

describe("PLAN_FEATURES table invariants", () => {
  it("keeps rank consistent with PLAN_RANK", () => {
    for (const plan of PLANS) expect(PLAN_FEATURES[plan].rank).toBe(PLAN_RANK[plan]);
  });

  it("labels each row with its own key", () => {
    for (const plan of PLANS) expect(PLAN_FEATURES[plan].plan).toBe(plan);
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
      expect(PLAN_FEATURES.Pro[key], key).toBeGreaterThanOrEqual(PLAN_FEATURES.Free[key]);
      expect(PLAN_FEATURES.Premium[key], key).toBeGreaterThanOrEqual(PLAN_FEATURES.Pro[key]);
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
      if (PLAN_FEATURES.Free[key]) expect(PLAN_FEATURES.Pro[key], key).toBe(true);
      if (PLAN_FEATURES.Pro[key]) expect(PLAN_FEATURES.Premium[key], key).toBe(true);
    }
  });

  it("treats null AI limits as unlimited, so only higher tiers may use them", () => {
    // Free has a concrete cap; Pro/Premium relax it to null (= unlimited).
    expect(PLAN_FEATURES.Free.ai_tutor_daily_limit).toBe(10);
    expect(PLAN_FEATURES.Pro.ai_tutor_daily_limit).toBeNull();
    expect(PLAN_FEATURES.Premium.ai_tutor_daily_limit).toBeNull();
    expect(PLAN_FEATURES.Premium.ai_reports_per_period).toBeNull();
    expect(PLAN_FEATURES.Premium.ai_reports_period).toBeNull();
  });

  it("pairs a report period with every non-null report quota", () => {
    for (const plan of PLANS) {
      const row = PLAN_FEATURES[plan];
      if (row.ai_reports_per_period === null) expect(row.ai_reports_period, plan).toBeNull();
      else expect(row.ai_reports_period, plan).not.toBeNull();
    }
  });
});
