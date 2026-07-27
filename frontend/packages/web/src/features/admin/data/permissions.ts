import type { AdminMe } from "./types";

/**
 * Pure permission check used by the admin UI to decide what to render.
 * super_admin implicitly holds every permission. A null `me` (not an admin)
 * has nothing. This is UX only — the server authorizes every action.
 */
export function hasPermission(me: AdminMe | null, permission: string): boolean {
  if (!me) return false;
  if (me.roles.includes("super_admin")) return true;
  return me.permissions.includes(permission);
}
