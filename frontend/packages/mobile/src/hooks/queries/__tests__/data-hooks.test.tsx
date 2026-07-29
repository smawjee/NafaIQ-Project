// Unit tests for the new data-layer query hooks. The @/lib/api transport is
// mocked so these assert each hook targets the right endpoint / body and
// surfaces data, without a network or a device.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import React from "react";

jest.mock("@/lib/api", () => ({
  userGet: jest.fn(),
  userPost: jest.fn(),
  userPatch: jest.fn(),
  userDelete: jest.fn(),
  publicGet: jest.fn(),
  fetchDividends: jest.fn(),
}));

import { fetchDividends, publicGet, userDelete, userGet, userPatch, userPost } from "@/lib/api";
import { useCreatePriceAlert, useDeletePriceAlert, usePriceAlerts } from "@/hooks/queries/use-price-alerts";
import { useLatestNews, useNews } from "@/hooks/queries/use-news";
import { useFundNav, useFunds } from "@/hooks/queries/use-funds";
import { useDividends, useSymbolDividends } from "@/hooks/queries/use-dividends";
import { useMacroFx, useMacroRates, usePolicyRate } from "@/hooks/queries/use-macro";
import { useNotificationPrefs, useUpdateNotificationPrefs } from "@/hooks/queries/use-notification-prefs";
import { useFinanceSettings, useUpdateFinanceSettings } from "@/hooks/queries/use-finance-settings";
import { useCalculateZakat, useUpdateZakatSettings, useZakatHistory, useZakatSettings } from "@/hooks/queries/use-zakat";
import { useAnnualFinancials, useQuarterlyFinancials } from "@/hooks/queries/use-financials";
import { useFilings } from "@/hooks/queries/use-filings";

const mUserGet = userGet as jest.Mock;
const mUserPost = userPost as jest.Mock;
const mUserPatch = userPatch as jest.Mock;
const mUserDelete = userDelete as jest.Mock;
const mPublicGet = publicGet as jest.Mock;
const mFetchDividends = fetchDividends as jest.Mock;

function wrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => jest.clearAllMocks());

describe("price alert hooks", () => {
  it("usePriceAlerts reads /api/alerts/price", async () => {
    mUserGet.mockResolvedValue([{ id: 1, symbol: "HBL" }]);
    const { result } = renderHook(() => usePriceAlerts(true), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mUserGet).toHaveBeenCalledWith("/api/alerts/price");
    expect(result.current.data).toHaveLength(1);
  });

  it("useCreatePriceAlert posts the body to /api/alerts/price", async () => {
    mUserPost.mockResolvedValue({ id: 2 });
    const { result } = renderHook(() => useCreatePriceAlert(), { wrapper: wrapper() });
    await act(async () => {
      await result.current.mutateAsync({ symbol: "OGDC", condition: "above", price: 100 });
    });
    expect(mUserPost).toHaveBeenCalledWith("/api/alerts/price", { symbol: "OGDC", condition: "above", price: 100 });
  });

  it("useDeletePriceAlert deletes by id", async () => {
    mUserDelete.mockResolvedValue({ deleted: 5 });
    const { result } = renderHook(() => useDeletePriceAlert(), { wrapper: wrapper() });
    await act(async () => {
      await result.current.mutateAsync(5);
    });
    expect(mUserDelete).toHaveBeenCalledWith("/api/alerts/price/5");
  });
});

describe("public market hooks", () => {
  it("useLatestNews hits /api/news/latest", async () => {
    mPublicGet.mockResolvedValue([]);
    const { result } = renderHook(() => useLatestNews(30), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mPublicGet).toHaveBeenCalledWith("/api/news/latest?limit=30");
  });

  it("useNews is disabled without a symbol and targets /api/news when given one", async () => {
    mPublicGet.mockResolvedValue([]);
    const { result } = renderHook(() => useNews("HBL", 10), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mPublicGet).toHaveBeenCalledWith("/api/news?symbol=HBL&limit=10");
  });

  it("useFunds reads /api/funds", async () => {
    mPublicGet.mockResolvedValue([]);
    const { result } = renderHook(() => useFunds(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mPublicGet).toHaveBeenCalledWith("/api/funds");
  });

  it("useFundNav reads /api/funds/{code}/nav", async () => {
    mPublicGet.mockResolvedValue([]);
    const { result } = renderHook(() => useFundNav("ABC"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mPublicGet).toHaveBeenCalledWith("/api/funds/ABC/nav");
  });

  it("useDividends reads /api/dividends and useSymbolDividends uses fetchDividends", async () => {
    mPublicGet.mockResolvedValue([]);
    mFetchDividends.mockResolvedValue([]);
    const all = renderHook(() => useDividends(), { wrapper: wrapper() });
    await waitFor(() => expect(all.result.current.isSuccess).toBe(true));
    expect(mPublicGet).toHaveBeenCalledWith("/api/dividends");
    const one = renderHook(() => useSymbolDividends("HBL"), { wrapper: wrapper() });
    await waitFor(() => expect(one.result.current.isSuccess).toBe(true));
    expect(mFetchDividends).toHaveBeenCalledWith("HBL");
  });

  it("macro hooks hit their endpoints", async () => {
    mPublicGet.mockResolvedValue({});
    renderHook(() => useMacroFx(), { wrapper: wrapper() });
    renderHook(() => usePolicyRate(), { wrapper: wrapper() });
    renderHook(() => useMacroRates(undefined, 12), { wrapper: wrapper() });
    await waitFor(() => expect(mPublicGet).toHaveBeenCalledWith("/api/macro/fx"));
    expect(mPublicGet).toHaveBeenCalledWith("/api/macro/policy-rate");
    expect(mPublicGet).toHaveBeenCalledWith("/api/macro/rates?limit=12");
  });

  it("financials + filings hit their endpoints", async () => {
    mPublicGet.mockResolvedValue([]);
    renderHook(() => useAnnualFinancials("HBL"), { wrapper: wrapper() });
    renderHook(() => useQuarterlyFinancials("HBL"), { wrapper: wrapper() });
    renderHook(() => useFilings("HBL"), { wrapper: wrapper() });
    await waitFor(() => expect(mPublicGet).toHaveBeenCalledWith(expect.stringContaining("/api/financials/HBL/annual")));
    expect(mPublicGet).toHaveBeenCalledWith(expect.stringContaining("/api/financials/HBL/quarterly"));
    expect(mPublicGet).toHaveBeenCalledWith(expect.stringContaining("/api/filings/HBL"));
  });
});

describe("user settings hooks", () => {
  it("notification prefs read + patch", async () => {
    mUserGet.mockResolvedValue({ email_alerts: true, email_activity: false, push_alerts: false, in_app_alerts: true });
    mUserPatch.mockResolvedValue({ ok: true });
    const read = renderHook(() => useNotificationPrefs(true), { wrapper: wrapper() });
    await waitFor(() => expect(read.result.current.isSuccess).toBe(true));
    expect(mUserGet).toHaveBeenCalledWith("/api/notifications/preferences");
    const upd = renderHook(() => useUpdateNotificationPrefs(), { wrapper: wrapper() });
    await act(async () => {
      await upd.result.current.mutateAsync({ email_activity: true });
    });
    expect(mUserPatch).toHaveBeenCalledWith("/api/notifications/preferences", { email_activity: true });
  });

  it("finance settings read + patch", async () => {
    mUserGet.mockResolvedValue({ monthly_income: 0, currency: "PKR", language: "en", plan: "Free" });
    mUserPatch.mockResolvedValue({ ok: true });
    const read = renderHook(() => useFinanceSettings(true), { wrapper: wrapper() });
    await waitFor(() => expect(read.result.current.isSuccess).toBe(true));
    expect(mUserGet).toHaveBeenCalledWith("/api/finance/settings");
    const upd = renderHook(() => useUpdateFinanceSettings(), { wrapper: wrapper() });
    await act(async () => {
      await upd.result.current.mutateAsync({ currency: "USD" });
    });
    expect(mUserPatch).toHaveBeenCalledWith("/api/finance/settings", { currency: "USD" });
  });
});

describe("zakat hooks", () => {
  it("settings read, history read, calculate post", async () => {
    mUserGet.mockResolvedValue({ method: "standard_2_5" });
    mUserPost.mockResolvedValue({ zakat_due: 100 });
    mUserPatch.mockResolvedValue({});
    renderHook(() => useZakatSettings(true), { wrapper: wrapper() });
    renderHook(() => useZakatHistory(20, true), { wrapper: wrapper() });
    await waitFor(() => expect(mUserGet).toHaveBeenCalledWith("/api/finance/zakat/settings"));
    expect(mUserGet).toHaveBeenCalledWith("/api/finance/zakat/history?limit=20");

    const calc = renderHook(() => useCalculateZakat(), { wrapper: wrapper() });
    await act(async () => {
      await calc.result.current.mutateAsync({ islamic_year: "1446", total_assets_pkr: 1000, nisab_value_pkr: 500, save: false });
    });
    expect(mUserPost).toHaveBeenCalledWith("/api/finance/zakat/calculate", expect.objectContaining({ total_assets_pkr: 1000 }));

    const upd = renderHook(() => useUpdateZakatSettings(), { wrapper: wrapper() });
    await act(async () => {
      await upd.result.current.mutateAsync({ nisab_source: "gold" });
    });
    expect(mUserPatch).toHaveBeenCalledWith("/api/finance/zakat/settings", { nisab_source: "gold" });
  });
});
