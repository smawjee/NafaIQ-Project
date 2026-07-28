// Default MSW handlers.
//
// Shapes here are transcribed from the FastAPI response models in
// backend/src/app/schemas/*.py — NOT invented. If a backend field is renamed,
// the corresponding test should fail, which is the whole point of keeping the
// fixtures here rather than inline in each test.
import { http, HttpResponse } from "msw";

/** Matches whatever VITE_API_URL resolves to, plus the 127.0.0.1 default. */
const api = (path: string) => `*/api${path}`;

/** backend/src/app/schemas/finance.py :: FinanceSummaryResponse */
export const financeSummary = {
  month: "2026-07",
  income: 45_000,
  fixed_income: 250_000,
  total_income: 295_000,
  expenses: 120_000,
  savings: 175_000,
  savings_rate: 59.32,
  last_month_income: 280_000,
  last_month_expense: 130_000,
  last_month_savings: 150_000,
};

/** backend/src/app/schemas/profile.py :: plan payload */
export const profilePlan = { plan: "free", plan_expires_at: null };

export const handlers = [
  http.get(api("/finance/summary"), () => HttpResponse.json(financeSummary)),
  http.get(api("/finance/transactions"), () => HttpResponse.json([])),
  http.get(api("/finance/budgets"), () => HttpResponse.json([])),
  http.get(api("/finance/bills"), () => HttpResponse.json([])),
  http.get(api("/finance/goals"), () => HttpResponse.json([])),
  http.get(api("/profile/plan"), () => HttpResponse.json(profilePlan)),
  http.get(api("/health"), () => HttpResponse.json({ status: "ok" })),
];
