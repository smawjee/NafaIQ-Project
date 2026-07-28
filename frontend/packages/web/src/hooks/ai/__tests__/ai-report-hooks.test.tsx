/**
 * The quota-sensitive contract of the daily-cached AI report hooks.
 *
 * The source comments in use-dashboard-recommendation.ts call this out as
 * critical and it had no test: `?refresh=true` is a real generation that CHARGES
 * the user's report quota, so it must be reachable only from an explicit click.
 * Every automatic trigger (mount, focus, reconnect, interval, retry) has to stay
 * off, and a failed refresh must not retry.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

const mockGetDashboardRecommendation = vi.fn();
const mockGetMarketBrief = vi.fn();
const mockGetStockReport = vi.fn();
const mockLang = vi.fn();

vi.mock("@/lib/ai/reports-client", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/ai/reports-client")>("@/lib/ai/reports-client");
  return {
    ...actual,
    getDashboardRecommendation: (...a: unknown[]) => mockGetDashboardRecommendation(...a),
    getMarketBrief: (...a: unknown[]) => mockGetMarketBrief(...a),
    generateStockReport: (...a: unknown[]) => mockGetStockReport(...a),
  };
});
vi.mock("@/hooks/use-lang", () => ({ useLang: () => mockLang() }));

import { ReportError } from "@/lib/ai/reports-client";
import { useDashboardRecommendation } from "@/hooks/ai/use-dashboard-recommendation";
import { useMarketBrief } from "@/hooks/ai/use-market-brief";
import { makeHookWrapper } from "@/test-utils";

const REPORT = { headline: "Cached brief", sections: [] };
const FRESH = { headline: "Freshly generated", sections: [] };

beforeEach(() => {
  mockGetDashboardRecommendation.mockReset();
  mockGetMarketBrief.mockReset();
  mockGetStockReport.mockReset();
  mockLang.mockReset();
  mockLang.mockReturnValue({ lang: "en" });
});

/** Both hooks implement the identical contract, so both are held to it. */
const HOOKS = [
  {
    name: "useDashboardRecommendation",
    hook: useDashboardRecommendation,
    fetcher: () => mockGetDashboardRecommendation,
    key: (lang: string) => ["ai", "dashboard-recommendation", lang],
  },
  {
    name: "useMarketBrief",
    hook: useMarketBrief,
    fetcher: () => mockGetMarketBrief,
    key: (lang: string) => ["ai", "market-brief", lang],
  },
] as const;

describe.each(HOOKS)("$name", ({ hook, fetcher, key }) => {
  function render(enabled = true) {
    const { Wrapper, queryClient } = makeHookWrapper();
    return { ...renderHook(() => hook(enabled), { wrapper: Wrapper }), queryClient };
  }

  it("reads the cached report without asking for a regeneration", async () => {
    fetcher().mockResolvedValue(REPORT);

    const { result } = render();

    await waitFor(() => expect(result.current.data).toEqual(REPORT));
    // Second argument is the `refresh` flag: undefined/false = free cached read.
    expect(fetcher()).toHaveBeenCalledTimes(1);
    expect(fetcher()).toHaveBeenCalledWith("en");
  });

  it("does not fetch at all while disabled (the dismiss switch)", () => {
    fetcher().mockResolvedValue(REPORT);

    render(false);

    expect(fetcher()).not.toHaveBeenCalled();
  });

  it("threads the active language into the request and the cache key", async () => {
    mockLang.mockReturnValue({ lang: "ur" });
    fetcher().mockResolvedValue(REPORT);

    const { result, queryClient } = render();

    await waitFor(() => expect(result.current.data).toEqual(REPORT));
    expect(fetcher()).toHaveBeenCalledWith("ur");
    expect(queryClient.getQueryData(key("ur"))).toEqual(REPORT);
    expect(queryClient.getQueryData(key("en"))).toBeUndefined();
  });

  it("charges quota only when refresh() is called explicitly", async () => {
    fetcher().mockResolvedValue(REPORT);
    const { result } = render();
    await waitFor(() => expect(result.current.data).toEqual(REPORT));

    expect(fetcher()).toHaveBeenCalledTimes(1);
    expect(fetcher()).not.toHaveBeenCalledWith("en", true);

    fetcher().mockResolvedValue(FRESH);
    act(() => result.current.refresh());

    await waitFor(() => expect(fetcher()).toHaveBeenCalledWith("en", true));
  });

  it("seeds the cache from refresh() instead of invalidating (no second GET)", async () => {
    fetcher().mockResolvedValue(REPORT);
    const { result, queryClient } = render();
    await waitFor(() => expect(result.current.data).toEqual(REPORT));

    fetcher().mockResolvedValue(FRESH);
    act(() => result.current.refresh());

    await waitFor(() => expect(queryClient.getQueryData(key("en"))).toEqual(FRESH));
    // 1 initial read + 1 refresh. An invalidate-based implementation would make
    // a third call to re-read what the mutation already returned.
    expect(fetcher()).toHaveBeenCalledTimes(2);
  });

  it("never retries a failed refresh — each attempt costs another quota unit", async () => {
    fetcher().mockResolvedValue(REPORT);
    const { result } = render();
    await waitFor(() => expect(result.current.data).toEqual(REPORT));

    fetcher().mockRejectedValue(new ReportError("quota", "Daily report limit reached", 429));
    act(() => result.current.refresh());

    await waitFor(() => expect(result.current.refreshError).toBeInstanceOf(ReportError));
    expect(fetcher()).toHaveBeenCalledTimes(2);
    expect(result.current.isRefreshing).toBe(false);
  });

  it("does not retry a quota error on the read path either", async () => {
    fetcher().mockRejectedValue(new ReportError("quota", "Daily report limit reached", 429));

    const { result } = render();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(fetcher()).toHaveBeenCalledTimes(1);
  });

  it("retries a network error, but at most twice", async () => {
    fetcher().mockRejectedValue(new ReportError("network", "Network request failed"));

    const { result } = render();

    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 10_000 });
    // failureCount < 2 => the initial attempt plus 2 retries.
    expect(fetcher()).toHaveBeenCalledTimes(3);
  });

  it("keeps every automatic refetch trigger disabled", async () => {
    fetcher().mockResolvedValue(REPORT);
    const { result, queryClient } = render();
    await waitFor(() => expect(result.current.data).toEqual(REPORT));

    const options = queryClient.getQueryCache().find({ queryKey: key("en") })?.options as
      Record<string, unknown> | undefined;

    expect(options?.refetchOnMount).toBe(false);
    expect(options?.refetchOnWindowFocus).toBe(false);
    expect(options?.refetchOnReconnect).toBe(false);
    expect(options?.refetchInterval).toBe(false);
    expect(options?.staleTime).toBe(24 * 60 * 60 * 1000);
  });
});
