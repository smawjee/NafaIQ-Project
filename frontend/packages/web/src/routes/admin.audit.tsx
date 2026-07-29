import { createFileRoute } from "@tanstack/react-router";
import { AdminAudit } from "@/features/admin/pages/Audit";
import { coerceInt, coerceStr } from "@/features/admin/data/tableSearch";

const STATUSES = ["success", "failure"] as const;
const RANGES = ["24h", "7d", "30d", "90d"] as const;
const PAGE_SIZES = [25, 50, 100];

/**
 * Optional throughout — an absent param means "not filtered", which keeps a
 * shared audit URL readable. The actor pair is what makes "everything this
 * administrator did" a link worth sending.
 */
export interface AdminAuditSearch {
  action?: string;
  status?: (typeof STATUSES)[number];
  range?: (typeof RANGES)[number];
  actor?: string;
  actorLabel?: string;
  page?: number;
  size?: number;
}

export const Route = createFileRoute("/admin/audit")({
  validateSearch: (search: Record<string, unknown>): AdminAuditSearch => {
    const out: AdminAuditSearch = {};

    const action = coerceStr(search.action, 100);
    if (action) out.action = action;

    if (typeof search.status === "string" && STATUSES.includes(search.status as never))
      out.status = search.status as AdminAuditSearch["status"];
    if (typeof search.range === "string" && RANGES.includes(search.range as never))
      out.range = search.range as AdminAuditSearch["range"];

    // The id is what filters; the label is display-only, so it is only carried
    // when there is an id for it to describe.
    const actor = coerceStr(search.actor, 64);
    if (actor) {
      out.actor = actor;
      const label = coerceStr(search.actorLabel, 200);
      if (label) out.actorLabel = label;
    }

    if (search.page !== undefined) {
      const page = coerceInt(search.page, 1, 1);
      if (page > 1) out.page = page;
    }
    if (search.size !== undefined) {
      const size = coerceInt(search.size, 50);
      if (PAGE_SIZES.includes(size) && size !== 50) out.size = size;
    }

    return out;
  },
  component: AdminAudit,
});
