import { createFileRoute } from "@tanstack/react-router";
import { AdminSubscriptions } from "@/features/admin/pages/Subscriptions";
import { coerceEnum, coerceInt, coerceStr } from "@/features/admin/data/tableSearch";

const PLANS = ["Free", "Pro", "Premium"] as const;
const TABS = ["distribution", "entitlements"] as const;
const PAGE_SIZES = [25, 50, 100];

export interface AdminSubscriptionsSearch {
  q?: string;
  plan?: (typeof PLANS)[number];
  page?: number;
  size?: number;
  tab?: (typeof TABS)[number];
}

export const Route = createFileRoute("/admin/subscriptions")({
  validateSearch: (search: Record<string, unknown>): AdminSubscriptionsSearch => {
    const out: AdminSubscriptionsSearch = {};
    const q = coerceStr(search.q);
    if (q) out.q = q;
    if (typeof search.plan === "string" && PLANS.includes(search.plan as never))
      out.plan = search.plan as AdminSubscriptionsSearch["plan"];
    if (typeof search.tab === "string" && TABS.includes(search.tab as never))
      out.tab = coerceEnum(search.tab, TABS, "distribution");
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
  component: AdminSubscriptions,
});
