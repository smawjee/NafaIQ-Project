import { describe, expect, it, vi, beforeEach } from "vitest";

const mockNavigate = vi.fn();
const mockUseAuth = vi.fn();
const mockUseAdmin = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
}));
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => mockUseAuth(),
}));
vi.mock("@/features/admin/data/useAdmin", () => ({
  useAdmin: () => mockUseAdmin(),
}));

import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { render, screen } from "@/test-utils";

const CHILD = "admin dashboard content";

function renderGuard() {
  return render(
    <AdminGuard>
      <p>{CHILD}</p>
    </AdminGuard>,
  );
}

/** Only the fields AdminGuard actually reads. */
const authed = { user: { id: "u1" }, loading: false };
const anonymous = { user: null, loading: false };
const bootstrapping = { user: null, loading: true };

beforeEach(() => {
  mockNavigate.mockClear();
  mockUseAuth.mockReset();
  mockUseAdmin.mockReset();
});

describe("AdminGuard", () => {
  it("renders children for a signed-in admin", () => {
    mockUseAuth.mockReturnValue(authed);
    mockUseAdmin.mockReturnValue({ isAdmin: true, isLoading: false });

    renderGuard();

    expect(screen.getByText(CHILD)).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("sends an anonymous visitor to /auth carrying the redirect back to /admin", () => {
    mockUseAuth.mockReturnValue(anonymous);
    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: false });

    renderGuard();

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/auth",
      search: { redirect: "/admin" },
    });
    expect(screen.queryByText(CHILD)).not.toBeInTheDocument();
  });

  it("bounces a signed-in non-admin to /app rather than showing an error", () => {
    mockUseAuth.mockReturnValue(authed);
    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: false });

    renderGuard();

    expect(mockNavigate).toHaveBeenCalledWith({ to: "/app" });
    expect(screen.queryByText(CHILD)).not.toBeInTheDocument();
  });

  it("waits while auth is still bootstrapping instead of bouncing to /auth", () => {
    // The redirect must not fire on first paint: `loading` is true before the
    // Supabase session resolves, and an admin refreshing /admin would otherwise
    // be kicked to /auth every time.
    mockUseAuth.mockReturnValue(bootstrapping);
    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: true });

    renderGuard();

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.queryByText(CHILD)).not.toBeInTheDocument();
  });

  it("waits while the admin role is still being fetched for a signed-in user", () => {
    mockUseAuth.mockReturnValue(authed);
    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: true });

    renderGuard();

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.queryByText(CHILD)).not.toBeInTheDocument();
  });

  it("redirects once the admin check resolves to false after loading", () => {
    mockUseAuth.mockReturnValue(authed);
    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: true });
    const { rerender } = renderGuard();
    expect(mockNavigate).not.toHaveBeenCalled();

    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: false });
    rerender(
      <AdminGuard>
        <p>{CHILD}</p>
      </AdminGuard>,
    );

    expect(mockNavigate).toHaveBeenCalledWith({ to: "/app" });
  });

  it("shows a spinner, not blank space, while resolving", () => {
    mockUseAuth.mockReturnValue(bootstrapping);
    mockUseAdmin.mockReturnValue({ isAdmin: false, isLoading: true });

    const { container } = renderGuard();

    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });
});
