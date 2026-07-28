import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminAuditSearch } from "@/routes/admin.audit";
import { adminApi } from "@/features/admin/data/client";
import type { AuditEntry } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  Button,
  CodeBlock,
  DataRow,
  DataTable,
  DateRangeFilter,
  Drawer,
  EmptyBlock,
  FilterBar,
  FilterSelect,
  formatPkt,
  humanizeAction,
  PageHeader,
  Panel,
  Pagination,
  presetToSince,
  relativeTime,
  RoleBadge,
  SearchInput,
  SectionLabel,
  StatusBadge,
  type Column,
  type DateRangePreset,
} from "@/features/admin/components/ui";

const STATUS_OPTIONS = [
  { value: "success", label: "Success" },
  { value: "failure", label: "Failure" },
];

export function AdminAudit() {
  const { t } = useLang();
  // Filters live in the URL: "everything this admin did in the last 7 days"
  // becomes a link you can paste into a ticket.
  const { search, setSearch, setFilter } = useTableSearch<AdminAuditSearch>("/admin/audit");
  const action = search.action ?? "";
  const status = search.status ?? "";
  const range = (search.range ?? "") as DateRangePreset;
  const page = search.page ?? 1;
  const pageSize = search.size ?? 50;
  const actor = search.actor
    ? { id: search.actor, label: search.actorLabel ?? search.actor }
    : null;

  const [detail, setDetail] = useState<AuditEntry | null>(null);

  const since = presetToSince(range);
  const activeFilters = [action, status, range, actor].filter(Boolean).length;

  function clearFilters() {
    setFilter({
      action: undefined,
      status: undefined,
      range: undefined,
      actor: undefined,
      actorLabel: undefined,
    });
  }

  function filterByActor(next: { id: string; label: string }) {
    setFilter({ actor: next.id, actorLabel: next.label });
  }

  function setPage(p: number) {
    setSearch({ page: p });
  }

  const q = useQuery({
    queryKey: ["admin-audit", action, status, since, actor?.id, page, pageSize],
    queryFn: () =>
      adminApi.listAudit({
        action: action || undefined,
        status: status || undefined,
        since: since ?? undefined,
        actor_user_id: actor?.id,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
    staleTime: 10_000,
  });

  // `filterByActor` is stable enough for this table (it only closes over
  // setState setters), and the column set is otherwise static.
  const columns = useMemo<Column<AuditEntry>[]>(
    () => [
      {
        id: "created_at",
        header: "When",
        width: "w-36",
        hideable: false,
        exportValue: (r) => r.created_at,
        cell: (r) => (
          <span className="whitespace-nowrap text-text-muted" title={formatPkt(r.created_at)}>
            {relativeTime(r.created_at)}
          </span>
        ),
      },
      {
        id: "actor",
        header: "Actor",
        exportValue: (r) => r.actor_email ?? "system",
        cell: (r) => (
          <div className="flex min-w-0 items-center gap-2">
            <Avatar email={r.actor_email} size="sm" />
            {r.actor_user_id ? (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  filterByActor({ id: r.actor_user_id!, label: r.actor_email ?? r.actor_user_id! });
                }}
                title={`Show only actions by ${r.actor_email ?? r.actor_user_id}`}
                className="truncate text-start text-text-secondary transition-colors hover:text-primary hover:underline"
              >
                {r.actor_email ?? r.actor_user_id}
              </button>
            ) : (
              <span className="truncate text-text-muted">system</span>
            )}
          </div>
        ),
      },
      {
        id: "action",
        header: "Action",
        hideable: false,
        exportValue: (r) => r.action,
        cell: (r) => (
          <div className="min-w-0">
            <div className="truncate font-medium text-text-primary">{humanizeAction(r.action)}</div>
            <code className="truncate text-[11px] text-text-muted">{r.action}</code>
          </div>
        ),
      },
      {
        id: "resource",
        header: "Resource",
        secondary: true,
        exportValue: (r) => (r.resource_type ? `${r.resource_type}:${r.resource_id ?? ""}` : ""),
        cell: (r) =>
          r.resource_type ? (
            <span className="text-text-secondary">
              <Badge tone="neutral">{r.resource_type}</Badge>
              {r.resource_id && (
                <code className="ms-1.5 text-[11px] text-text-muted">{r.resource_id}</code>
              )}
            </span>
          ) : (
            <span className="text-text-muted">—</span>
          ),
      },
      {
        id: "status",
        header: "Status",
        exportValue: (r) => r.status,
        cell: (r) => <StatusBadge status={r.status} />,
      },
      {
        id: "detail",
        header: "",
        align: "end",
        hideable: false,
        cell: (r) => (
          <Button size="sm" variant="ghost" onClick={() => setDetail(r)}>
            Details
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Audit Log")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Audit Log") }]}
        description="Every administrative action, append-only and immutable. Written in the same transaction as the change it records, so the log can never drift from reality. All times in PKT."
        meta={q.data && <Badge tone="neutral">{q.data.meta.total.toLocaleString()} entries</Badge>}
      />

      <Panel flush>
        <DataTable
          label="Audit log"
          columns={columns}
          rows={q.data?.items ?? []}
          getRowId={(r) => String(r.id)}
          isLoading={q.isLoading}
          isError={q.isError}
          onRetry={() => void q.refetch()}
          onRowClick={setDetail}
          activeRowId={detail ? String(detail.id) : null}
          hasFilters={activeFilters > 0}
          onClearFilters={clearFilters}
          emptyState={
            <EmptyBlock
              label="No admin actions recorded yet"
              hint="Suspensions, tier changes, role grants and flag edits all land here."
            />
          }
          toolbar={
            <FilterBar active={activeFilters} onClear={clearFilters}>
              <SearchInput
                value={action}
                // replace: don't push a history entry per keystroke.
                onChange={(v) => setFilter({ action: v || undefined }, { replace: true })}
                placeholder="Filter by action, e.g. admin.user.tier"
                className="max-w-xs"
              />
              <FilterSelect
                label="Status"
                allLabel="All statuses"
                value={status}
                onChange={(v) =>
                  setFilter({ status: (v || undefined) as AdminAuditSearch["status"] })
                }
                options={STATUS_OPTIONS}
              />
              <DateRangeFilter
                value={range}
                onChange={(v) =>
                  setFilter({ range: (v || undefined) as AdminAuditSearch["range"] })
                }
              />
              {actor && (
                <span className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 px-2.5 text-xs font-medium text-primary">
                  Actor: <span className="max-w-[12rem] truncate">{actor.label}</span>
                  <button
                    onClick={() => setFilter({ actor: undefined, actorLabel: undefined })}
                    aria-label="Clear actor filter"
                    className="cursor-pointer rounded hover:opacity-70"
                  >
                    <X className="h-3 w-3" aria-hidden />
                  </button>
                </span>
              )}
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
                pageSizeOptions={[25, 50, 100]}
              />
            )
          }
        />
      </Panel>

      <AuditDetail entry={detail} onClose={() => setDetail(null)} onFilterActor={filterByActor} />
    </div>
  );
}

function AuditDetail({
  entry,
  onClose,
  onFilterActor,
}: {
  entry: AuditEntry | null;
  onClose: () => void;
  onFilterActor: (a: { id: string; label: string }) => void;
}) {
  return (
    <Drawer
      open={!!entry}
      onOpenChange={(open) => !open && onClose()}
      title={entry ? humanizeAction(entry.action) : "Audit entry"}
      description={entry?.action}
    >
      {entry && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={entry.status} />
            {entry.resource_type && <Badge tone="neutral">{entry.resource_type}</Badge>}
          </div>

          <div>
            <SectionLabel className="mb-1.5">Who & when</SectionLabel>
            <dl className="rounded-lg border border-border bg-surface-alt px-3 py-1">
              <DataRow
                label="Actor"
                value={
                  entry.actor_user_id ? (
                    <button
                      onClick={() => {
                        onFilterActor({
                          id: entry.actor_user_id!,
                          label: entry.actor_email ?? entry.actor_user_id!,
                        });
                        onClose();
                      }}
                      className="text-primary hover:underline"
                    >
                      {entry.actor_email ?? entry.actor_user_id}
                    </button>
                  ) : (
                    "system"
                  )
                }
              />
              {entry.actor_roles.length > 0 && (
                <DataRow
                  label="Actor roles"
                  value={
                    <span className="flex flex-wrap justify-end gap-1">
                      {entry.actor_roles.map((r) => (
                        <RoleBadge key={r} role={r} />
                      ))}
                    </span>
                  }
                />
              )}
              <DataRow label="Timestamp" value={formatPkt(entry.created_at)} />
              {entry.ip && (
                <DataRow label="IP" value={<code className="text-xs">{entry.ip}</code>} />
              )}
              {entry.request_id && (
                <DataRow
                  label="Request ID"
                  value={<code className="text-xs">{entry.request_id}</code>}
                />
              )}
            </dl>
          </div>

          {(entry.resource_id || entry.target_user_id) && (
            <div>
              <SectionLabel className="mb-1.5">Target</SectionLabel>
              <dl className="rounded-lg border border-border bg-surface-alt px-3 py-1">
                {entry.resource_id && (
                  <DataRow
                    label="Resource ID"
                    value={<code className="text-xs">{entry.resource_id}</code>}
                  />
                )}
                {entry.target_user_id && (
                  <DataRow
                    label="Target user"
                    value={
                      <Link
                        to="/admin/users/$userId"
                        params={{ userId: entry.target_user_id }}
                        onClick={onClose}
                        className="text-xs text-primary hover:underline"
                      >
                        {entry.target_user_id}
                      </Link>
                    }
                  />
                )}
              </dl>
            </div>
          )}

          {entry.reason && (
            <div>
              <SectionLabel className="mb-1.5">Reason</SectionLabel>
              <p className="rounded-lg border border-border bg-surface-alt px-3 py-2.5 text-sm text-text-primary">
                {entry.reason}
              </p>
            </div>
          )}

          {(entry.before != null || entry.after != null) && (
            <div className="grid gap-3 sm:grid-cols-2">
              {entry.before != null && <CodeBlock label="Before" value={entry.before} />}
              {entry.after != null && <CodeBlock label="After" value={entry.after} />}
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}
