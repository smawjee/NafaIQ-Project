import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { AlertTriangle, Bug, CheckCircle2, EyeOff, Users as UsersIcon } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminErrorsSearch } from "@/routes/admin.errors";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { ErrorEventRow, ErrorGroup } from "@/features/admin/data/types";
import {
  Badge,
  Button,
  CodeBlock,
  DataRow,
  DataTable,
  DateRangeFilter,
  Drawer,
  EmptyBlock,
  ErrorBlock,
  FilterBar,
  FilterSelect,
  formatNumber,
  formatPkt,
  KpiCard,
  KpiSkeleton,
  Pagination,
  PageHeader,
  Panel,
  PermissionDenied,
  presetToSince,
  relativeTime,
  SearchInput,
  SectionLabel,
  StatusBadge,
  type Column,
  type DateRangePreset,
} from "@/features/admin/components/ui";

const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "investigating", label: "Investigating" },
  { value: "resolved", label: "Resolved" },
  { value: "ignored", label: "Ignored" },
];
const SOURCE_OPTIONS = [
  { value: "client", label: "Client" },
  { value: "server", label: "Server" },
];

export function AdminErrors() {
  const { t } = useLang();
  const { can } = useAdmin();

  // Filters live in the URL so a triage view is shareable and survives refresh —
  // "open server errors, last 24h" is a link you can paste into a ticket.
  const { search, setSearch, setFilter } = useTableSearch<AdminErrorsSearch>("/admin/errors");
  const query = search.q ?? "";
  // Default to open: an unfiltered error list is mostly resolved noise.
  const status = search.status ?? "open";
  const source = search.source ?? "";
  const range = (search.range ?? "") as DateRangePreset;
  const page = search.page ?? 1;
  const pageSize = search.size ?? 25;
  const openGroup = search.fp ?? null;
  const setOpenGroup = (fp: string | null) => setSearch({ fp: fp ?? undefined });

  const since = presetToSince(range);
  const activeFilters = [query, status, source, range].filter(Boolean).length;

  function clearFilters() {
    setFilter({ q: undefined, status: undefined, source: undefined, range: undefined });
  }
  const setPage = (p: number) => setSearch({ page: p });

  const summaryQ = useQuery({
    queryKey: ["admin-errors-summary"],
    queryFn: adminApi.errorSummary,
    staleTime: 30_000,
  });

  const q = useQuery({
    queryKey: ["admin-errors", query, status, source, since, page, pageSize],
    queryFn: () =>
      adminApi.listErrors({
        query: query || undefined,
        status: status || undefined,
        source: source || undefined,
        since: since ?? undefined,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });

  const columns = useMemo<Column<ErrorGroup>[]>(
    () => [
      {
        id: "message",
        header: t("Error"),
        hideable: false,
        exportValue: (r) => r.message,
        cell: (r) => (
          <div className="min-w-0">
            <div className="truncate font-medium text-text-primary" title={r.message}>
              {r.message}
            </div>
            <div className="flex items-center gap-1.5">
              <Badge tone={r.source === "server" ? "warning" : "neutral"}>{r.source}</Badge>
              {r.route && <code className="truncate text-[11px] text-text-muted">{r.route}</code>}
            </div>
          </div>
        ),
      },
      {
        id: "users_affected",
        header: t("Users"),
        align: "end",
        exportValue: (r) => r.users_affected,
        // The number that decides priority: 40 people hitting a bug matters more
        // than 400 occurrences from one person stuck in a retry loop.
        cell: (r) => (
          <span
            className={cn(
              "tabular font-semibold",
              r.users_affected > 0 ? "text-text-primary" : "text-text-muted",
            )}
          >
            {formatNumber(r.users_affected)}
          </span>
        ),
      },
      {
        id: "event_count",
        header: t("Events"),
        align: "end",
        secondary: true,
        exportValue: (r) => r.event_count,
        cell: (r) => (
          <span className="tabular text-text-secondary">{formatNumber(r.event_count)}</span>
        ),
      },
      {
        id: "last_seen",
        header: t("Last seen"),
        exportValue: (r) => r.last_seen,
        cell: (r) => (
          <span className="whitespace-nowrap text-text-muted" title={formatPkt(r.last_seen)}>
            {relativeTime(r.last_seen)}
          </span>
        ),
      },
      {
        id: "status",
        header: t("Status"),
        exportValue: (r) => r.status,
        cell: (r) => <StatusBadge status={r.status} />,
      },
      {
        id: "open",
        header: "",
        align: "end",
        hideable: false,
        cell: (r) => (
          <Button size="sm" variant="ghost" onClick={() => setOpenGroup(r.fingerprint)}>
            {t("Details")}
          </Button>
        ),
      },
    ],
    [t],
  );

  if (!can("errors.read")) {
    return (
      <Panel>
        <PermissionDenied permission="errors.read" />
      </Panel>
    );
  }

  const s = summaryQ.data?.errors;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Errors")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Errors") }]}
        description={t(
          "Failures captured automatically from the app and the API, grouped so one bug is one row. Personal data is stripped before storage; events are kept for 30 days.",
        )}
      />

      {summaryQ.isLoading ? (
        <KpiSkeleton count={3} />
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <KpiCard
            label={t("Open issues")}
            value={formatNumber(s?.open_groups)}
            icon={<AlertTriangle className="h-4 w-4" />}
            hint={t("Distinct unresolved failures")}
          />
          <KpiCard
            label={t("Active (24h)")}
            value={formatNumber(s?.active_24h)}
            icon={<Bug className="h-4 w-4" />}
            hint={t("Groups that fired in the last day")}
          />
          <KpiCard
            label={t("Events (24h)")}
            value={formatNumber(s?.events_24h)}
            icon={<UsersIcon className="h-4 w-4" />}
            hint={t("Total occurrences")}
          />
        </div>
      )}

      <Panel flush>
        <DataTable
          label="Errors"
          columns={columns}
          rows={q.data?.items ?? []}
          getRowId={(r) => r.fingerprint}
          isLoading={q.isLoading}
          isError={q.isError}
          onRetry={() => void q.refetch()}
          onRowClick={(r) => setOpenGroup(r.fingerprint)}
          activeRowId={openGroup}
          hasFilters={activeFilters > 0}
          onClearFilters={clearFilters}
          emptyState={
            <EmptyBlock
              label={t("No errors captured")}
              hint={t(
                "Nothing has failed in this window. Client crashes and API 5xxs appear here automatically.",
              )}
            />
          }
          toolbar={
            <FilterBar active={activeFilters} onClear={clearFilters}>
              <SearchInput
                value={query}
                onChange={(v) => setFilter({ q: v || undefined }, { replace: true })}
                placeholder={t("Search message or route…")}
                className="max-w-xs"
              />
              <FilterSelect
                label={t("Status")}
                allLabel={t("All statuses")}
                value={status}
                onChange={(v) =>
                  setFilter({ status: (v || undefined) as AdminErrorsSearch["status"] })
                }
                options={STATUS_OPTIONS}
              />
              <FilterSelect
                label={t("Source")}
                allLabel={t("All sources")}
                value={source}
                onChange={(v) =>
                  setFilter({ source: (v || undefined) as AdminErrorsSearch["source"] })
                }
                options={SOURCE_OPTIONS}
              />
              <DateRangeFilter
                value={range}
                onChange={(v) =>
                  setFilter({ range: (v || undefined) as AdminErrorsSearch["range"] })
                }
              />
            </FilterBar>
          }
          footer={
            q.data && (
              <Pagination
                page={q.data.meta.page}
                pageSize={q.data.meta.page_size}
                total={q.data.meta.total}
                onPage={setPage}
                onPageSize={(n) => setFilter({ size: n })}
              />
            )
          }
        />
      </Panel>

      <ErrorDetail fingerprint={openGroup} onClose={() => setOpenGroup(null)} />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function ErrorDetail({
  fingerprint,
  onClose,
}: {
  fingerprint: string | null;
  onClose: () => void;
}) {
  const { t } = useLang();
  const { can } = useAdmin();
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: ["admin-error", fingerprint],
    queryFn: () => adminApi.getError(fingerprint!),
    enabled: !!fingerprint,
  });

  const mut = useMutation({
    mutationFn: (v: { status: string; note?: string }) =>
      adminApi.triageError(fingerprint!, v.status, v.note),
    onSuccess: () => {
      toast.success(t("Error updated"));
      void qc.invalidateQueries({ queryKey: ["admin-error", fingerprint] });
      void qc.invalidateQueries({ queryKey: ["admin-errors"] });
      void qc.invalidateQueries({ queryKey: ["admin-errors-summary"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const group = q.data?.group;
  const events = q.data?.events ?? [];

  return (
    <Drawer
      open={!!fingerprint}
      onOpenChange={(v) => !v && onClose()}
      title={group?.message ?? t("Error")}
      description={group?.route ?? undefined}
      width="lg"
      footer={
        can("errors.write") &&
        group && (
          <>
            <Button
              variant="ghost"
              icon={<EyeOff className="h-3.5 w-3.5" />}
              loading={mut.isPending}
              onClick={() => mut.mutate({ status: "ignored" })}
            >
              {t("Ignore")}
            </Button>
            <Button
              variant="secondary"
              loading={mut.isPending}
              onClick={() => mut.mutate({ status: "investigating" })}
            >
              {t("Investigating")}
            </Button>
            <Button
              variant="primary"
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              loading={mut.isPending}
              onClick={() => mut.mutate({ status: "resolved" })}
            >
              {t("Mark resolved")}
            </Button>
          </>
        )
      }
    >
      {q.isError ? (
        <ErrorBlock onRetry={() => void q.refetch()} />
      ) : !group ? (
        <EmptyBlock label={t("Loading…")} />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={group.status} />
            <Badge tone={group.source === "server" ? "warning" : "neutral"}>{group.source}</Badge>
          </div>

          {group.status === "resolved" && (
            <div className="rounded-lg border border-bull/30 bg-bull/10 px-3 py-2 text-xs text-bull">
              {t(
                "Marked resolved. If this error is captured again it will reopen automatically — a bug that recurs was not fixed.",
              )}
            </div>
          )}

          <dl className="rounded-lg border border-border bg-surface-alt px-3 py-1">
            <DataRow label={t("Occurrences")} value={formatNumber(group.event_count)} />
            <DataRow label={t("First seen")} value={formatPkt(group.first_seen)} />
            <DataRow label={t("Last seen")} value={formatPkt(group.last_seen)} />
            <DataRow
              label={t("Fingerprint")}
              value={<code className="text-[11px]">{group.fingerprint}</code>}
            />
          </dl>

          {group.sample_stack && <CodeBlock label={t("Sample stack")} value={group.sample_stack} />}

          <div>
            <SectionLabel className="mb-1.5">{t("Recent occurrences")}</SectionLabel>
            {events.length === 0 ? (
              <EmptyBlock label={t("No stored occurrences (they may have aged out).")} />
            ) : (
              <ul className="space-y-1.5">
                {events.map((e: ErrorEventRow) => (
                  <li
                    key={e.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface-alt px-3 py-2 text-xs"
                  >
                    <span className="text-text-muted">{formatPkt(e.created_at)}</span>
                    {e.user_id ? (
                      <Link
                        to="/admin/users/$userId"
                        params={{ userId: e.user_id }}
                        onClick={onClose}
                        className="truncate text-primary hover:underline"
                      >
                        {e.user_email ?? e.user_id}
                      </Link>
                    ) : (
                      <span className="text-text-muted">{t("Signed out")}</span>
                    )}
                    {e.route && <code className="truncate text-text-secondary">{e.route}</code>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}
