import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";
import { adminApi } from "./client";
import { hasPermission } from "./permissions";
import type { AdminMe } from "./types";

/**
 * Resolves the signed-in user's admin roles/permissions from the backend
 * (GET /api/admin/me). A 403 (non-admin) is a NORMAL outcome, not an error —
 * it resolves to `isAdmin: false` so callers can hide admin affordances.
 *
 * This is a UX signal only. The server authorizes every admin action on its
 * own; a tampered client cannot gain access by faking this hook.
 */
export function useAdmin() {
  const { user } = useAuth();
  const query = useQuery<AdminMe | null>({
    queryKey: ["admin-me", user?.id],
    enabled: !!user,
    // Cached for the session: the admin check is a per-user backend call fired
    // on every authenticated load, so keep it infrequent. Cheap and rarely
    // changes; refetch on a fresh session.
    staleTime: 10 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    retry: false,
    queryFn: async () => {
      try {
        return await adminApi.me();
      } catch {
        // 403 for non-admins (and any transient failure) → treat as "not admin".
        return null;
      }
    },
  });

  const me = query.data ?? null;
  const isSuperAdmin = (me?.roles ?? []).includes("super_admin");

  return {
    me,
    isLoading: query.isLoading,
    isAdmin: !!me,
    isSuperAdmin,
    roles: me?.roles ?? [],
    can: (permission: string) => hasPermission(me, permission),
  };
}
