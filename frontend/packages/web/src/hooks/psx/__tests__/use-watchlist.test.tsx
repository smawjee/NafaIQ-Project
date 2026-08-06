import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Provider } from "react-redux";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/store";

const mocks = vi.hoisted(() => ({
  userPost: vi.fn(),
  userDelete: vi.fn(),
  clearWatchlist: vi.fn(),
  select: vi.fn(),
}));

vi.mock("@/lib/psx/client", () => ({
  userGet: vi.fn(),
  userPost: mocks.userPost,
  userDelete: mocks.userDelete,
  clearWatchlist: mocks.clearWatchlist,
}));

vi.mock("@/integrations/supabase/client", () => ({
  supabase: {
    from: () => ({
      select: () => ({ order: () => mocks.select() }),
    }),
  },
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "real@user.com" } }),
}));

vi.mock("@/lib/demo", () => ({ isDemoUser: () => false }));

import { useWatchlist } from "@/hooks/psx/use-watchlist";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <Provider store={store}>
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    </Provider>
  );
}

async function mountWithSymbols(symbols: string[]) {
  mocks.select.mockResolvedValue({ data: symbols.map((symbol) => ({ symbol })) });
  const { result } = renderHook(() => useWatchlist(), { wrapper });
  await waitFor(() => expect(result.current.symbols).toEqual(symbols));
  return result;
}

describe("useWatchlist remove", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("removes the symbol when the server accepts the delete", async () => {
    mocks.userDelete.mockResolvedValue(undefined);
    const result = await mountWithSymbols(["HBL", "ENGRO"]);

    await act(() => result.current.remove("HBL"));

    expect(mocks.userDelete).toHaveBeenCalledWith("/api/watchlist/HBL");
    expect(result.current.symbols).toEqual(["ENGRO"]);
  });

  it("restores the symbol when the server rejects the delete", async () => {
    // Silently swallowing this left the row gone from the UI but still on the
    // server — it reappeared on the next reload with no explanation.
    mocks.userDelete.mockRejectedValue(new Error("500"));
    const result = await mountWithSymbols(["HBL", "ENGRO"]);

    await act(async () => {
      await expect(result.current.remove("HBL")).rejects.toThrow();
    });

    expect(result.current.symbols).toEqual(["HBL", "ENGRO"]);
  });
});

describe("useWatchlist add", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("adds the symbol when the server accepts it", async () => {
    mocks.userPost.mockResolvedValue(undefined);
    const result = await mountWithSymbols(["HBL"]);

    await act(() => result.current.add("pso"));

    expect(mocks.userPost).toHaveBeenCalledWith("/api/watchlist", { symbol: "PSO" });
    expect(result.current.symbols).toContain("PSO");
  });

  it("rolls the symbol back when the server rejects it (e.g. quota exceeded)", async () => {
    mocks.userPost.mockRejectedValue(new Error("watchlist limit reached"));
    const result = await mountWithSymbols(["HBL"]);

    await act(async () => {
      await expect(result.current.add("PSO")).rejects.toThrow();
    });

    expect(result.current.symbols).toEqual(["HBL"]);
  });
});
