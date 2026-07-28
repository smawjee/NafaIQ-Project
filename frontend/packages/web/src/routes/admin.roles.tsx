import { createFileRoute } from "@tanstack/react-router";
import { AdminRoles } from "@/features/admin/pages/Roles";
import { coerceEnum, coerceStr } from "@/features/admin/data/tableSearch";

const TABS = ["admins", "roles", "matrix"] as const;

export interface AdminRolesSearch {
  q?: string;
  /** Which tab is open — so a shared link lands on the right one. */
  tab?: (typeof TABS)[number];
}

export const Route = createFileRoute("/admin/roles")({
  validateSearch: (search: Record<string, unknown>): AdminRolesSearch => {
    const out: AdminRolesSearch = {};
    const q = coerceStr(search.q, 100);
    if (q) out.q = q;
    if (typeof search.tab === "string" && TABS.includes(search.tab as never))
      out.tab = coerceEnum(search.tab, TABS, "admins");
    return out;
  },
  component: AdminRoles,
});
