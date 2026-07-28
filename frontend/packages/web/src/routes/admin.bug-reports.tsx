import { createFileRoute } from "@tanstack/react-router";
import { AdminBugReports } from "@/features/admin/pages/BugReports";
import { coerceInt, coerceStr } from "@/features/admin/data/tableSearch";

const STATUSES = ["open", "investigating", "resolved", "wont_fix"] as const;
const CATEGORIES = ["bug", "data", "billing", "feature", "other"] as const;
const PAGE_SIZES = [25, 50, 100];

export interface AdminBugReportsSearch {
  q?: string;
  status?: (typeof STATUSES)[number];
  category?: (typeof CATEGORIES)[number];
  page?: number;
  size?: number;
  /** Open report — so a specific report can be linked into a ticket. */
  id?: number;
}

export const Route = createFileRoute("/admin/bug-reports")({
  validateSearch: (search: Record<string, unknown>): AdminBugReportsSearch => {
    const out: AdminBugReportsSearch = {};
    const q = coerceStr(search.q, 200);
    if (q) out.q = q;
    if (typeof search.status === "string" && STATUSES.includes(search.status as never))
      out.status = search.status as AdminBugReportsSearch["status"];
    if (typeof search.category === "string" && CATEGORIES.includes(search.category as never))
      out.category = search.category as AdminBugReportsSearch["category"];
    if (search.id !== undefined) {
      const id = coerceInt(search.id, 0, 1);
      if (id > 0) out.id = id;
    }
    if (search.page !== undefined) {
      const page = coerceInt(search.page, 1, 1);
      if (page > 1) out.page = page;
    }
    if (search.size !== undefined) {
      const size = coerceInt(search.size, 25);
      if (PAGE_SIZES.includes(size) && size !== 25) out.size = size;
    }
    return out;
  },
  component: AdminBugReports,
});
