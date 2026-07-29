import { createFileRoute } from "@tanstack/react-router";
import { AdminFlags } from "@/features/admin/pages/Flags";
import { coerceStr } from "@/features/admin/data/tableSearch";

export interface AdminFlagsSearch {
  q?: string;
}

export const Route = createFileRoute("/admin/flags")({
  validateSearch: (search: Record<string, unknown>): AdminFlagsSearch => {
    const q = coerceStr(search.q, 100);
    return q ? { q } : {};
  },
  component: AdminFlags,
});
