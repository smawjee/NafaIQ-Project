import { useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminSubscriptionsSearch } from "@/routes/admin.subscriptions";
import { useAdmin } from "@/features/admin/data/useAdmin";
import { PlanEntitlements } from "./PlanEntitlements";
import type { UserListItem } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  Button,
  DataTable,
  DonutChart,
  EmptyBlock,
  ErrorBlock,
  FilterBar,
  FilterSelect,
  formatPkt,
  KpiCard,
  KpiSkeleton,
  Pagination,
  PageHeader,
  Panel,
  PermissionDenied,
  SearchInput,
  StatusBadge,
  type Column,
} from "@/features/admin/components/ui";

const PLANS = ["Free", "Pro", "Premium"];
const PLAN_OPTIONS = PLANS.map((p) => ({ value: p, label: p }));

export function AdminSubscriptions() {
  const { t } = useLang();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { can } = useAdmin();
  const canWrite = can("users.tier.write");

  const { search, setSearch, setFilter } =
    useTableSearch<AdminSubscriptionsSearch>("/admin/subscriptions");
  const query = search.q ?? "";
  const plan = search.plan ?? "";
  const page = search.page ?? 1;
  const pageSize = search.size ?? 25;
  const setPage = (p: number) => setSearch({ page: p });

  const overviewQ = useQuery({
    queryKey: ["admin-overview"],
    queryFn: adminApi.overview,
    staleTime: 30_000,
  });

  const usersQ = useQuery({
    queryKey: ["admin-users", query, "", plan, null, page, pageSize],
    queryFn: () =>
      adminApi.listUsers({
        query: query || undefined,
        plan: plan || undefined,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
    enabled: can("users.read"),
  });

  const tierMut = useMutation({
    mutationFn: (v: { id: string; plan: string }) => adminApi.changeTier(v.id, v.plan),
    onSuccess: () => {
      toast.success("Subscription tier updated");
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
      void qc.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const tiers = overviewQ.data?.tiers;
  // Memoised so the `segments` memo below isn't invalidated by a fresh `{}`
  // fallback identity on every render.
  const tierData = useMemo(() => (tiers?.data ?? {}) as Record<string, number>, [tiers?.data]);
  const segments = useMemo(
    () => Object.entries(tierData).map(([label, value]) => ({ label, value: Number(value) || 0 })),
    [tierData],
  );
  const total = segments.reduce((s, x) => s + x.value, 0);
  const paidCount = segments.filter((s) => s.label !== "Free").reduce((sum, s) => sum + s.value, 0);

  const activeFilters = [query, plan].filter(Boolean).length;
  function clearFilters() {
    setFilter({ q: undefined, plan: undefined });
  }

  const columns = useMemo<Column<UserListItem>[]>(
    () => [
      {
        id: "email",
        header: "User",
        hideable: false,
        exportValue: (r) => r.email ?? r.id,
        cell: (r) => (
          <div className="flex min-w-0 items-center gap-2.5">
            <Avatar email={r.email} size="sm" />
            <Link
              to="/admin/users/$userId"
              params={{ userId: r.id }}
              className="truncate font-medium text-text-primary hover:text-primary hover:underline"
            >
              {r.email ?? r.id}
            </Link>
          </div>
        ),
      },
      {
        id: "account_status",
        header: "Status",
        secondary: true,
        exportValue: (r) => r.account_status,
        cell: (r) => <StatusBadge status={r.account_status} />,
      },
      {
        id: "plan_selected",
        header: "Joined",
        secondary: true,
        exportValue: (r) => r.created_at,
        cell: (r) => <span className="text-text-muted">{formatPkt(r.created_at, false)}</span>,
      },
      {
        id: "plan",
        header: "Tier",
        align: "end",
        hideable: false,
        exportValue: (r) => r.plan,
        cell: (r) =>
          canWrite ? (
            // Inline segmented control — the whole point of this page is
            // changing a tier without a detour through the profile.
            <div
              className="flex justify-end gap-1"
              role="group"
              aria-label={`Tier for ${r.email ?? r.id}`}
            >
              {PLANS.map((p) => {
                const current = r.plan === p;
                return (
                  <button
                    key={p}
                    disabled={current || tierMut.isPending}
                    aria-pressed={current}
                    onClick={() =>
                      confirm({
                        title: `Change tier to ${p}?`,
                        description: `${r.email ?? r.id} will move from ${r.plan} to ${p}. The change is recorded in the audit log with both values.`,
                        confirmText: `Set ${p}`,
                        onConfirm: async () => {
                          await tierMut.mutateAsync({ id: r.id, plan: p });
                        },
                      })
                    }
                    className={cn(
                      "h-7 cursor-pointer rounded-md border px-2 text-xs font-medium transition-all",
                      current
                        ? "border-primary/40 bg-primary/12 text-primary"
                        : "border-border text-text-muted hover:border-border-hover hover:bg-hover hover:text-text-primary",
                      "disabled:cursor-default",
                    )}
                  >
                    {p}
                  </button>
                );
              })}
            </div>
          ) : (
            <Badge tone={r.plan === "Free" ? "neutral" : "accent"}>{r.plan}</Badge>
          ),
      },
    ],
    [canWrite, confirm, tierMut],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Subscriptions")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Subscriptions") }]}
        description={t(
          "Tier distribution and inline tier management, plus the entitlements each plan grants. There is no payment-provider integration yet — tiers are assigned manually and every change is audited.",
        )}
      />

      <Tabs.Root
        value={search.tab ?? "distribution"}
        onValueChange={(v) => setSearch({ tab: v as AdminSubscriptionsSearch["tab"] })}
      >
        <Tabs.List
          aria-label={t("Subscription sections")}
          className="flex flex-wrap gap-1 border-b border-border"
        >
          <TabTrigger value="distribution">{t("Distribution")}</TabTrigger>
          <TabTrigger value="entitlements">{t("Plan entitlements")}</TabTrigger>
        </Tabs.List>

        <Tabs.Content value="entitlements" className="pt-5 focus-visible:outline-none">
          <PlanEntitlements />
        </Tabs.Content>

        <Tabs.Content value="distribution" className="space-y-5 pt-5 focus-visible:outline-none">
          {overviewQ.isLoading ? (
            <KpiSkeleton count={3} />
          ) : overviewQ.isError ? (
            <Panel>
              <ErrorBlock onRetry={() => void overviewQ.refetch()} />
            </Panel>
          ) : (
            <div className="grid gap-3 sm:grid-cols-3">
              <KpiCard
                label="Total users"
                value={total.toLocaleString()}
                available={tiers?.available}
                hint="Across all tiers"
              />
              <KpiCard
                label="Paid tiers"
                value={paidCount.toLocaleString()}
                available={tiers?.available}
                hint={total > 0 ? `${((paidCount / total) * 100).toFixed(1)}% of base` : undefined}
              />
              <KpiCard
                label="Free tier"
                value={(tierData.Free ?? 0).toLocaleString()}
                available={tiers?.available}
                hint={
                  total > 0
                    ? `${(((tierData.Free ?? 0) / total) * 100).toFixed(1)}% of base`
                    : undefined
                }
              />
            </div>
          )}

          <div className="grid gap-4 xl:grid-cols-3">
            <Panel title="Tier distribution" className="xl:col-span-1">
              {overviewQ.isLoading ? (
                <div className="h-[200px] animate-pulse rounded-lg bg-muted" />
              ) : !tiers?.available ? (
                <EmptyBlock label="Tier data unavailable" />
              ) : (
                <DonutChart data={segments} centerLabel="users" />
              )}
            </Panel>

            <Panel
              title="Manage tiers"
              description={
                canWrite
                  ? "Change a user's plan directly from this list."
                  : "You have read-only access to subscription data."
              }
              className="xl:col-span-2"
              flush
            >
              {!can("users.read") ? (
                <PermissionDenied permission="users.read" />
              ) : (
                <DataTable
                  label="Subscriptions"
                  columns={columns}
                  rows={usersQ.data?.items ?? []}
                  getRowId={(r) => r.id}
                  isLoading={usersQ.isLoading}
                  isError={usersQ.isError}
                  onRetry={() => void usersQ.refetch()}
                  hasFilters={activeFilters > 0}
                  onClearFilters={clearFilters}
                  enableColumnControl={false}
                  toolbar={
                    <FilterBar active={activeFilters} onClear={clearFilters}>
                      <SearchInput
                        value={query}
                        onChange={(v) => setFilter({ q: v || undefined }, { replace: true })}
                        placeholder={t("Search users…")}
                        className="max-w-xs"
                      />
                      <FilterSelect
                        label={t("Plan")}
                        allLabel={t("All plans")}
                        value={plan}
                        onChange={(v) =>
                          setFilter({
                            plan: (v || undefined) as AdminSubscriptionsSearch["plan"],
                          })
                        }
                        options={PLAN_OPTIONS}
                      />
                    </FilterBar>
                  }
                  footer={
                    usersQ.data && (
                      <Pagination
                        page={usersQ.data.meta.page}
                        pageSize={usersQ.data.meta.page_size}
                        total={usersQ.data.meta.total}
                        onPage={setPage}
                        onPageSize={(n) => setFilter({ size: n })}
                      />
                    )
                  }
                />
              )}
            </Panel>
          </div>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function TabTrigger({ value, children }: { value: string; children: React.ReactNode }) {
  return (
    <Tabs.Trigger
      value={value}
      className={cn(
        "-mb-px inline-flex cursor-pointer items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium",
        "border-transparent text-text-muted transition-colors hover:text-text-primary",
        "data-[state=active]:border-primary data-[state=active]:text-primary",
      )}
    >
      {children}
    </Tabs.Trigger>
  );
}
