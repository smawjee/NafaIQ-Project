import { createFileRoute } from "@tanstack/react-router";
import { AdminErrors } from "@/features/admin/pages/Errors";
import { coerceInt, coerceStr } from "@/features/admin/data/tableSearch";

const STATUSES = ["open", "investigating", "resolved", "ignored"] as const;
const SOURCES = ["client", "server"] as const;
const RANGES = ["24h", "7d", "30d", "90d"] as const;
const PAGE_SIZES = [25, 50, 100];

/**
 * Optional throughout, defaults applied in the page — an absent param means
 * "not filtered", which keeps a shared triage URL readable.
 *
 * `status` is the exception worth noting: the page defaults it to "open"
 * because an unfiltered error list is mostly noise, but the param is still
 * omitted from the URL at that default so the clean link means "the default
 * view" rather than pinning a value that might change.
 */
export interface AdminErrorsSearch {
  q?: string;
  status?: (typeof STATUSES)[number];
  source?: (typeof SOURCES)[number];
  range?: (typeof RANGES)[number];
  page?: number;
  size?: number;
  /** Open group — makes a specific error a shareable link. */
  fp?: string;
}

export const Route = createFileRoute("/admin/errors")({
  validateSearch: (search: Record<string, unknown>): AdminErrorsSearch => {
    const out: AdminErrorsSearch = {};
    const q = coerceStr(search.q, 200);
    if (q) out.q = q;
    if (typeof search.status === "string" && STATUSES.includes(search.status as never))
      out.status = search.status as AdminErrorsSearch["status"];
    if (typeof search.source === "string" && SOURCES.includes(search.source as never))
      out.source = search.source as AdminErrorsSearch["source"];
    if (typeof search.range === "string" && RANGES.includes(search.range as never))
      out.range = search.range as AdminErrorsSearch["range"];
    const fp = coerceStr(search.fp, 64);
    if (fp) out.fp = fp;
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
  component: AdminErrors,
});
