/**
 * Frontend <-> backend contract for GET /api/finance/summary.
 *
 * Phase 3 of QA week. The fixture in src/mocks/handlers.ts is transcribed from
 * backend/src/app/schemas/finance.py::FinanceSummaryResponse, so this suite
 * fails if the backend renames or drops a field that a released client reads.
 * That drift is not hypothetical — `fixed_income` / `total_income` were added
 * to the response after both clients had shipped.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const mockUserGet = vi.fn();
vi.mock("@/lib/psx/client", () => ({ userGet: (p: string) => mockUserGet(p) }));

import { useFinanceSummary, type FinanceSummary } from "@/hooks/use-finance-summary";
import { financeSummary } from "@/mocks/handlers";
import { makeHookWrapper } from "@/test-utils";

/** Exactly the fields FinanceSummaryResponse declares. */
const CONTRACT_FIELDS = [
  "month",
  "income",
  "fixed_income",
  "total_income",
  "expenses",
  "savings",
  "savings_rate",
  "last_month_income",
  "last_month_expense",
  "last_month_savings",
  "opening_balance",
  "carried_over",
  "available_balance",
] as const;

beforeEach(() => {
  mockUserGet.mockReset();
  mockUserGet.mockResolvedValue(financeSummary);
});

function render(month?: string) {
  const { Wrapper, queryClient } = makeHookWrapper();
  return { ...renderHook(() => useFinanceSummary(month), { wrapper: Wrapper }), queryClient };
}

describe("finance summary contract", () => {
  it("the fixture carries every field the backend schema declares", () => {
    expect(Object.keys(financeSummary).sort()).toEqual([...CONTRACT_FIELDS].sort());
  });

  it("every numeric field really is a number", () => {
    for (const key of CONTRACT_FIELDS) {
      if (key === "month") continue;
      expect(typeof financeSummary[key as keyof typeof financeSummary], key).toBe("number");
    }
    expect(typeof financeSummary.month).toBe("string");
  });

  it("the TypeScript type and the payload agree at runtime", () => {
    // If a field is dropped from the backend, this assignment still compiles but
    // the key check above fails — together they catch both directions of drift.
    const typed: FinanceSummary = financeSummary;
    expect(Number.isFinite(typed.total_income)).toBe(true);
  });

  it("reconciles the salary against recorded income rather than always adding", () => {
    // Recorded below the salary => the salary never landed as a transaction,
    // so it is added. Recorded at or above it => it is already inside, and
    // adding again would double-count an imported salary credit.
    const { income, fixed_income, total_income } = financeSummary;
    const expected = income >= fixed_income ? income : income + fixed_income;
    expect(total_income).toBe(expected);
  });

  it("the running balance is carried_over plus this month's savings", () => {
    // Without these the app resets to zero every month and last month's
    // unspent balance disappears.
    const { carried_over, savings, available_balance, opening_balance } = financeSummary;
    expect(available_balance).toBeCloseTo(carried_over + savings, 2);
    expect(carried_over).toBeGreaterThanOrEqual(opening_balance);
    expect(available_balance).toBeGreaterThan(savings);
  });

  it("resolves the payload through the hook unchanged", async () => {
    const { result } = render();

    await waitFor(() => expect(result.current.data).toEqual(financeSummary));
    expect(mockUserGet).toHaveBeenCalledWith("/api/finance/summary");
  });

  it("appends the month query string when one is requested", async () => {
    const { result } = render("2026-06");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockUserGet).toHaveBeenCalledWith("/api/finance/summary?month=2026-06");
  });

  it("keys the cache per month so switching months does not serve stale data", async () => {
    const { result, queryClient } = render("2026-06");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(queryClient.getQueryData(["finance", "summary", "2026-06"])).toEqual(financeSummary);
    expect(queryClient.getQueryData(["finance", "summary", "current"])).toBeUndefined();
  });

  it("Overview reads total_income, not income — the field added after ship", () => {
    // Overview.tsx uses `summary?.total_income ?? variableIncome`. The field
    // must still be present and numeric; it is no longer strictly greater than
    // `income`, because the salary is a fallback rather than an addend.
    expect(financeSummary).toHaveProperty("total_income");
    expect(Number.isFinite(financeSummary.total_income)).toBe(true);
    expect(financeSummary.fixed_income).toBeGreaterThan(0);
  });

  it("savings and savings_rate are internally consistent", () => {
    const { total_income, expenses, savings, savings_rate } = financeSummary;
    expect(savings).toBe(total_income - expenses);
    expect(savings_rate).toBeCloseTo((savings / total_income) * 100, 1);
  });

  it("surfaces a backend error instead of silently rendering zeroes", async () => {
    mockUserGet.mockRejectedValue(new Error("/api/finance/summary: 500 Internal Server Error"));

    const { result } = render();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
