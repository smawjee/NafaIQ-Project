import { createFileRoute } from "@tanstack/react-router";
import { AdminUsers } from "@/features/admin/pages/Users";
import { coerceEnum, coerceInt, coerceStr } from "@/features/admin/data/tableSearch";

const STATUSES = ["active", "suspended", "restricted"] as const;
const PLANS = ["Free", "Pro", "Premium"] as const;
/** Mirrors the backend's `_SORT_KEYS` whitelist in api/admin/users.py. */
const SORTS = [
  "created_at",
  "last_sign_in_at",
  "email",
  "display_name",
  "plan",
  "account_status",
] as const;
const PAGE_SIZES = [25, 50, 100];

/**
 * Every field is OPTIONAL, and the validator omits anything absent.
 *
 * Two reasons. First, `/admin/users/$userId` is a *child* of this route and so
 * inherits this schema — if these were required, every `<Link>` to a user
 * profile would have to restate the whole filter set. Second, an absent param
 * genuinely means "not filtered", which is different from `q=""`; keeping it
 * out leaves shared URLs clean and readable.
 *
 * The page supplies the defaults.
 */
export interface AdminUsersSearch {
  q?: string;
  status?: (typeof STATUSES)[number];
  plan?: (typeof PLANS)[number];
  sort?: (typeof SORTS)[number];
  order?: "asc" | "desc";
  page?: number;
  size?: number;
}

export const Route = createFileRoute("/admin/users")({
  // Runs on every navigation, including a hand-edited URL, so it clamps rather
  // than throws — a bad value degrades to "not set" instead of breaking the page.
  validateSearch: (search: Record<string, unknown>): AdminUsersSearch => {
    const out: AdminUsersSearch = {};

    const q = coerceStr(search.q);
    if (q) out.q = q;

    if (typeof search.status === "string" && STATUSES.includes(search.status as never))
      out.status = search.status as AdminUsersSearch["status"];
    if (typeof search.plan === "string" && PLANS.includes(search.plan as never))
      out.plan = search.plan as AdminUsersSearch["plan"];

    // Sort is only meaningful as a pair; drop a half-specified one.
    if (typeof search.sort === "string" && SORTS.includes(search.sort as never)) {
      out.sort = search.sort as AdminUsersSearch["sort"];
      out.order = coerceEnum(search.order, ["asc", "desc"] as const, "desc");
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
  component: AdminUsers,
});
