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
    // Cache a CONFIRMED result for a few minutes (admin status rarely changes),
    // but never cache a transient failure — see queryFn.
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    // Recover automatically when the backend comes back after being unreachable.
    refetchOnReconnect: true,
    retry: 1,
    queryFn: async () => {
      try {
        return await adminApi.me();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "";
        // A definitive "you're not an admin" (401/403) is a real, cacheable
        // answer → hide admin affordances.
        if (msg.includes(" 401 ") || msg.includes(" 403 ")) return null;
        // Anything else (backend down, network, 5xx) is NOT an answer. Throw so
        // it isn't cached as "not admin" — the query stays in an error state and
        // re-checks on the next mount/navigation/reconnect, so a brief backend
        // outage can never durably hide the Admin link.
        throw e;
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
