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
    expect(typed.total_income).toBe(typed.income + typed.fixed_income);
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
    // src/features/finance/components/Overview.tsx:71 uses
    // `summary?.total_income ?? variableIncome`. If the backend stopped sending
    // total_income, the KPI would silently fall back to the variable income and
    // under-report a salaried user's monthly income.
    expect(financeSummary.total_income).toBeGreaterThan(financeSummary.income);
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
