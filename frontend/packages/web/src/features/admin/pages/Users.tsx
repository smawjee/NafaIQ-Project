import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ExternalLink, ShieldCheck, ShieldOff, Wallet } from "lucide-react";
import { toast } from "sonner";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminUsersSearch } from "@/routes/admin.users";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { UserListItem } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  Button,
  DataTable,
  FilterBar,
  FilterSelect,
  formatPkt,
  Pagination,
  PageHeader,
  Panel,
  relativeTime,
  SearchInput,
  StatusBadge,
  type Column,
  type SortState,
} from "@/features/admin/components/ui";
import { UserQuickView } from "./UserQuickView";

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "restricted", label: "Restricted" },
];

const PLANS = ["Free", "Pro", "Premium"] as const;
const PLAN_OPTIONS = PLANS.map((p) => ({ value: p, label: p }));

export function AdminUsers() {
  const { t } = useLang();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { can } = useAdmin();

  // Filter/sort/page live in the URL so a filtered view is shareable, survives
  // a refresh, and steps correctly with browser back/forward.
  const { search, setSearch, setFilter } = useTableSearch<AdminUsersSearch>("/admin/users");
  // Defaults live here rather than in validateSearch, so an unfiltered URL stays
  // clean (`/admin/users`) instead of carrying every default as a query string.
  const query = search.q ?? "";
  const status = search.status ?? "";
  const plan = search.plan ?? "";
  const page = search.page ?? 1;
  const pageSize = search.size ?? 25;
  const sort: SortState = { id: search.sort ?? "created_at", dir: search.order ?? "desc" };

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [quickView, setQuickView] = useState<string | null>(null);

  // Selection is only offered when at least one bulk action is available —
  // otherwise the checkboxes would be a control that does nothing.
  const canSuspend = can("users.suspend");
  const canTier = can("users.tier.write");
  const canBulk = canSuspend || canTier;

  const activeFilters = [query, status, plan].filter(Boolean).length;

  function clearFilters() {
    // undefined removes the param entirely rather than leaving `?q=`.
    setFilter({ q: undefined, status: undefined, plan: undefined });
    setSelected(new Set());
  }

  /** Filter change: back to page 1 and drop the selection, in one navigation. */
  function onFilter(patch: Partial<AdminUsersSearch>, replace = false) {
    setFilter(patch, { replace });
    setSelected(new Set());
  }

  function setPage(p: number) {
    // Selection is per-page (bulk actions only ever act on visible rows), so
    // paging clears it rather than leaving an invisible pending set.
    setSearch({ page: p });
    setSelected(new Set());
  }

  const q = useQuery({
    queryKey: ["admin-users", query, status, plan, sort, page, pageSize],
    queryFn: () =>
      adminApi.listUsers({
        query: query || undefined,
        status: status || undefined,
        plan: plan || undefined,
        sort: sort.id,
        order: sort.dir,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });

  /**
   * Bulk status change. The API is per-user, so this fans out and reports the
   * real tally — partial failures are surfaced rather than swallowed.
   */
  const bulkStatus = useMutation({
    mutationFn: async (v: { ids: string[]; status: string }) => {
      const results = await Promise.allSettled(
        v.ids.map((id) =>
          adminApi.changeStatus(id, v.status, `Bulk ${v.status} from admin console`),
        ),
      );
      return {
        ok: results.filter((r) => r.status === "fulfilled").length,
        failed: results.filter((r) => r.status === "rejected").length,
      };
    },
    onSuccess: ({ ok, failed }) => {
      if (failed === 0) toast.success(`${ok} account${ok === 1 ? "" : "s"} updated`);
      else toast.warning(`${ok} updated, ${failed} failed`);
      setSelected(new Set());
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
      void qc.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  /** Bulk tier change. Same fan-out/report contract as bulkStatus. */
  const bulkTier = useMutation({
    mutationFn: async (v: { ids: string[]; plan: string }) => {
      const results = await Promise.allSettled(
        v.ids.map((id) => adminApi.changeTier(id, v.plan, `Bulk tier change from admin console`)),
      );
      return {
        ok: results.filter((r) => r.status === "fulfilled").length,
        failed: results.filter((r) => r.status === "rejected").length,
      };
    },
    onSuccess: ({ ok, failed }) => {
      if (failed === 0) toast.success(`${ok} tier${ok === 1 ? "" : "s"} updated`);
      else toast.warning(`${ok} updated, ${failed} failed`);
      setSelected(new Set());
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
      void qc.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const columns = useMemo<Column<UserListItem>[]>(
    () => [
      {
        id: "email",
        header: "User",
        sortable: true,
        hideable: false,
        exportValue: (r) => r.email ?? r.id,
        cell: (r) => (
          <div className="flex min-w-0 items-center gap-2.5">
            <Avatar email={r.email} size="sm" />
            <div className="min-w-0">
              <Link
                to="/admin/users/$userId"
                params={{ userId: r.id }}
                onClick={(e) => e.stopPropagation()}
                className="block truncate font-medium text-text-primary hover:text-primary hover:underline"
              >
                {r.email ?? r.id}
              </Link>
              {r.display_name && (
                <span className="block truncate text-xs text-text-muted">{r.display_name}</span>
              )}
            </div>
          </div>
        ),
      },
      {
        id: "plan",
        header: "Plan",
        sortable: true,
        exportValue: (r) => r.plan,
        cell: (r) => <Badge tone={r.plan === "Free" ? "neutral" : "accent"}>{r.plan}</Badge>,
      },
      {
        id: "account_status",
        header: "Status",
        sortable: true,
        exportValue: (r) => r.account_status,
        cell: (r) => <StatusBadge status={r.account_status} />,
      },
      {
        id: "created_at",
        header: "Joined",
        sortable: true,
        secondary: true,
        exportValue: (r) => r.created_at,
        cell: (r) => (
          <span className="text-text-muted" title={formatPkt(r.created_at)}>
            {formatPkt(r.created_at, false)}
          </span>
        ),
      },
      {
        id: "last_sign_in_at",
        header: "Last seen",
        sortable: true,
        exportValue: (r) => r.last_sign_in_at,
        cell: (r) => (
          <span className="text-text-muted" title={formatPkt(r.last_sign_in_at)}>
            {relativeTime(r.last_sign_in_at)}
          </span>
        ),
      },
      {
        id: "actions",
        header: "",
        align: "end",
        hideable: false,
        cell: (r) => (
          <div className="flex items-center justify-end gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                setQuickView(r.id);
              }}
            >
              Inspect
            </Button>
            <Link
              to="/admin/users/$userId"
              params={{ userId: r.id }}
              onClick={(e) => e.stopPropagation()}
              aria-label={`Open full profile for ${r.email ?? r.id}`}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-hover hover:text-text-primary"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Users")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Users") }]}
        description="Search the whole user base, inspect an account inline, or open a profile to suspend, re-tier, note or grant roles."
        meta={q.data && <Badge tone="neutral">{q.data.meta.total.toLocaleString()} total</Badge>}
      />

      <Panel flush>
        <DataTable
          label="Users"
          columns={columns}
          rows={q.data?.items ?? []}
          getRowId={(r) => r.id}
          isLoading={q.isLoading}
          isError={q.isError}
          onRetry={() => void q.refetch()}
          sort={sort}
          onSortChange={(next) =>
            onFilter(
              next
                ? { sort: next.id as AdminUsersSearch["sort"], order: next.dir }
                : { sort: "created_at", order: "desc" },
            )
          }
          selectedIds={canBulk ? selected : undefined}
          onSelectionChange={canBulk ? setSelected : undefined}
          activeRowId={quickView}
          hasFilters={activeFilters > 0}
          onClearFilters={clearFilters}
          toolbar={
            <FilterBar active={activeFilters} onClear={clearFilters}>
              <SearchInput
                value={query}
                // replace: typing must not push one history entry per keystroke.
                onChange={(v) => onFilter({ q: v || undefined }, true)}
                placeholder={t("Search by email or name…")}
                className="max-w-xs"
              />
              <FilterSelect
                label={t("Status")}
                allLabel={t("All statuses")}
                value={status}
                onChange={(v) =>
                  onFilter({ status: (v || undefined) as AdminUsersSearch["status"] })
                }
                options={STATUS_OPTIONS}
              />
              <FilterSelect
                label={t("Plan")}
                allLabel={t("All plans")}
                value={plan}
                onChange={(v) => onFilter({ plan: (v || undefined) as AdminUsersSearch["plan"] })}
                options={PLAN_OPTIONS}
              />
            </FilterBar>
          }
          bulkActions={(ids) => (
            <>
              {canSuspend && (
                <Button
                  size="sm"
                  variant="danger"
                  icon={<ShieldOff className="h-3.5 w-3.5" />}
                  loading={bulkStatus.isPending}
                  onClick={() =>
                    confirm({
                      title: `Suspend ${ids.length} account${ids.length === 1 ? "" : "s"}?`,
                      description:
                        "Each account will be signed out and blocked from every authenticated action until reactivated. This is recorded in the audit log.",
                      confirmText: "Suspend all",
                      variant: "destructive",
                      onConfirm: async () => {
                        await bulkStatus.mutateAsync({ ids, status: "suspended" });
                      },
                    })
                  }
                >
                  Suspend
                </Button>
              )}
              {canSuspend && (
                <Button
                  size="sm"
                  variant="outline"
                  icon={<ShieldCheck className="h-3.5 w-3.5" />}
                  loading={bulkStatus.isPending}
                  onClick={() =>
                    confirm({
                      title: `Reactivate ${ids.length} account${ids.length === 1 ? "" : "s"}?`,
                      description: "Access will be restored immediately for each account.",
                      confirmText: "Reactivate all",
                      onConfirm: async () => {
                        await bulkStatus.mutateAsync({ ids, status: "active" });
                      },
                    })
                  }
                >
                  Reactivate
                </Button>
              )}
              {canTier && (
                <>
                  <span className="mx-1 h-4 w-px bg-border" aria-hidden />
                  {PLANS.map((p) => (
                    <Button
                      key={p}
                      size="sm"
                      variant="outline"
                      icon={<Wallet className="h-3.5 w-3.5" />}
                      loading={bulkTier.isPending}
                      onClick={() =>
                        confirm({
                          title: `Move ${ids.length} account${ids.length === 1 ? "" : "s"} to ${p}?`,
                          description: `Each selected account's plan will be set to ${p}. Every change is recorded individually in the audit log with its before/after value.`,
                          confirmText: `Set ${p}`,
                          onConfirm: async () => {
                            await bulkTier.mutateAsync({ ids, plan: p });
                          },
                        })
                      }
                    >
                      {p}
                    </Button>
                  ))}
                </>
              )}
            </>
          )}
          footer={
            q.data && (
              <Pagination
                page={q.data.meta.page}
                pageSize={q.data.meta.page_size}
                total={q.data.meta.total}
                onPage={setPage}
                onPageSize={(n) => onFilter({ size: n })}
              />
            )
          }
        />
      </Panel>

      <UserQuickView userId={quickView} onClose={() => setQuickView(null)} />
    </div>
  );
}
