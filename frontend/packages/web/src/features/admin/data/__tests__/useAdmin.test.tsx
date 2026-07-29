import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const mockMe = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("@/features/admin/data/client", () => ({
  adminApi: { me: () => mockMe() },
}));
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => mockUseAuth(),
}));

import { useAdmin } from "@/features/admin/data/useAdmin";
import { makeHookWrapper } from "@/test-utils";

const SUPER = { user_id: "u1", roles: ["super_admin"], permissions: [] };
const SCOPED = { user_id: "u1", roles: ["support_admin"], permissions: ["users.read"] };

beforeEach(() => {
  mockMe.mockReset();
  mockUseAuth.mockReset();
  mockUseAuth.mockReturnValue({ user: { id: "u1" } });
});

function render() {
  const { Wrapper, queryClient } = makeHookWrapper();
  return { ...renderHook(() => useAdmin(), { wrapper: Wrapper }), queryClient };
}

describe("useAdmin", () => {
  it("does not call the API at all when signed out", () => {
    mockUseAuth.mockReturnValue({ user: null });

    const { result } = render();

    expect(mockMe).not.toHaveBeenCalled();
    expect(result.current.isAdmin).toBe(false);
  });

  it("reports an admin and exposes their roles", async () => {
    mockMe.mockResolvedValue(SCOPED);

    const { result } = render();

    await waitFor(() => expect(result.current.isAdmin).toBe(true));
    expect(result.current.roles).toEqual(["support_admin"]);
    expect(result.current.isSuperAdmin).toBe(false);
    expect(result.current.me).toEqual(SCOPED);
  });

  it("flags super_admin", async () => {
    mockMe.mockResolvedValue(SUPER);

    const { result } = render();

    await waitFor(() => expect(result.current.isSuperAdmin).toBe(true));
  });

  it("delegates can() to hasPermission — super_admin gets everything", async () => {
    mockMe.mockResolvedValue(SUPER);

    const { result } = render();

    await waitFor(() => expect(result.current.isAdmin).toBe(true));
    expect(result.current.can("flags.write")).toBe(true);
  });

  it("grants a scoped admin only its mapped permissions", async () => {
    mockMe.mockResolvedValue(SCOPED);

    const { result } = render();

    await waitFor(() => expect(result.current.isAdmin).toBe(true));
    expect(result.current.can("users.read")).toBe(true);
    expect(result.current.can("flags.write")).toBe(false);
  });

  // --- the rule commit 80c1a05 introduced -------------------------------
  // "fix(admin): don't cache a transient backend failure as 'not admin'".

  it.each([" 401 ", " 403 "])(
    "treats a%sresponse as a definitive not-an-admin answer",
    async (code) => {
      mockMe.mockRejectedValue(new Error(`GET /api/admin/me:${code}Forbidden`));

      const { result } = render();

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      expect(result.current.isAdmin).toBe(false);
      expect(result.current.me).toBeNull();
    },
  );

  it("does NOT cache a 500 as 'not admin' — the query ends in an error state", async () => {
    mockMe.mockRejectedValue(new Error("GET /api/admin/me: 500 Internal Server Error"));

    const { result, queryClient } = render();

    // `retry: 1` is set inside the hook itself, so it survives the test
    // client's `retry: false` and the failure needs one backoff to settle.
    await waitFor(() => expect(result.current.isLoading).toBe(false), { timeout: 5_000 });
    expect(result.current.isAdmin).toBe(false);

    // The distinction that matters: a 401/403 resolves to cached `null` data,
    // a 5xx leaves the query errored with NO data, so the next mount re-checks
    // instead of durably hiding the Admin link.
    const state = queryClient.getQueryState(["admin-me", "u1"]);
    expect(state?.status).toBe("error");
    expect(state?.data).toBeUndefined();
  });

  it("caches a 403 as data so a real non-admin is not re-queried on every mount", async () => {
    mockMe.mockRejectedValue(new Error("GET /api/admin/me: 403 Forbidden"));

    const { result, queryClient } = render();

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const state = queryClient.getQueryState(["admin-me", "u1"]);
    expect(state?.status).toBe("success");
    expect(state?.data).toBeNull();
  });

  it("recovers once the backend returns after an outage", async () => {
    mockMe
      .mockRejectedValueOnce(new Error("GET /api/admin/me: 503 Service Unavailable"))
      .mockRejectedValueOnce(new Error("GET /api/admin/me: 503 Service Unavailable"))
      .mockResolvedValue(SUPER);

    const { result, queryClient } = render();

    await waitFor(() => expect(result.current.isLoading).toBe(false), { timeout: 5_000 });
    expect(result.current.isAdmin).toBe(false);

    await queryClient.refetchQueries({ queryKey: ["admin-me", "u1"] });

    await waitFor(() => expect(result.current.isAdmin).toBe(true), { timeout: 5_000 });
  });

  it("keys the cache by user id so switching accounts cannot reuse the answer", async () => {
    mockMe.mockResolvedValue(SUPER);
    const { result, queryClient } = render();
    await waitFor(() => expect(result.current.isAdmin).toBe(true));

    expect(queryClient.getQueryData(["admin-me", "u1"])).toEqual(SUPER);
    expect(queryClient.getQueryData(["admin-me", "u2"])).toBeUndefined();
  });
});
