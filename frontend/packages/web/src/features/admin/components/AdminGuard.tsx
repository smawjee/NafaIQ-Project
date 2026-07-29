import { type ReactNode, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useAdmin } from "@/features/admin/data/useAdmin";

/**
 * Client-side gate for the admin surface. This is UX only — it decides whether
 * to RENDER admin pages. The backend authorizes every admin API call on its own,
 * so a user who bypasses this guard still gets 403s and sees no data.
 *
 * Non-admins are bounced to /app rather than shown an error, so the admin area
 * simply doesn't exist for them.
 */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const { isAdmin, isLoading } = useAdmin();
  const navigate = useNavigate();

  const resolving = loading || (!!user && isLoading);

  useEffect(() => {
    if (resolving) return;
    if (!user) {
      navigate({ to: "/auth", search: { redirect: "/admin" } });
      return;
    }
    if (!isAdmin) {
      navigate({ to: "/app" });
    }
  }, [resolving, user, isAdmin, navigate]);

  if (resolving || !user || !isAdmin) {
    // Rendered inside `.admin-root` so the console theme is already applied —
    // otherwise the app theme paints for a frame and the console appears to
    // flash on every navigation into /admin.
    return (
      <div className="admin-root flex min-h-screen flex-col items-center justify-center gap-4 bg-background">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-primary/25 bg-primary/10">
          <ShieldCheck className="h-5 w-5 text-primary" aria-hidden />
        </div>
        <div
          className="flex items-center gap-2 text-sm text-text-muted"
          role="status"
          aria-live="polite"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          Verifying administrator access…
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
