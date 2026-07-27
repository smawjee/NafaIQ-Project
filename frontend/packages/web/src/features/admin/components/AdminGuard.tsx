import { type ReactNode, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
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
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
