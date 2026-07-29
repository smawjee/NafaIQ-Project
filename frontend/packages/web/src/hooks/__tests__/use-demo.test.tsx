import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockNavigate = vi.fn();
const mockSignInWithPassword = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    user: null,
    signInWithPassword: mockSignInWithPassword,
  }),
}));

import { DEMO_EMAIL, useDemo } from "@/hooks/use-demo";

describe("useDemo", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DEMO_PASSWORD", "demo-secret");
    mockNavigate.mockReset();
    mockSignInWithPassword.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("signs in and navigates to the requested route", async () => {
    mockSignInWithPassword.mockResolvedValue({ error: null });
    const { result } = renderHook(() => useDemo());

    await act(() => result.current.signInAsDemo({ redirectTo: "/portfolio" }));

    expect(mockSignInWithPassword).toHaveBeenCalledWith(DEMO_EMAIL, "demo-secret");
    expect(mockNavigate).toHaveBeenCalledWith({ to: "/portfolio" });
  });

  it("throws authentication failures instead of silently staying on the page", async () => {
    mockSignInWithPassword.mockResolvedValue({ error: "Invalid login credentials" });
    const { result } = renderHook(() => useDemo());

    await expect(result.current.signInAsDemo()).rejects.toThrow("Invalid login credentials");
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("throws a clear configuration error when the demo password is missing", async () => {
    vi.stubEnv("VITE_DEMO_PASSWORD", "");
    const { result } = renderHook(() => useDemo());

    await expect(result.current.signInAsDemo()).rejects.toThrow("Demo password not configured");
    expect(mockSignInWithPassword).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
