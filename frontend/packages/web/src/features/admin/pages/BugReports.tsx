import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CheckCircle2, Inbox, MessageSquare, XCircle } from "lucide-react";
import { toast } from "sonner";
import { useLang } from "@/hooks/use-lang";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminBugReportsSearch } from "@/routes/admin.bug-reports";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { BugReport } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  Button,
  DataRow,
  DataTable,
  Drawer,
  EmptyBlock,
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
  relativeTime,
  SearchInput,
  SectionLabel,
  StatusBadge,
  Textarea,
  type Column,
} from "@/features/admin/components/ui";

const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "investigating", label: "Investigating" },
  { value: "resolved", label: "Resolved" },
  { value: "wont_fix", label: "Won't fix" },
];
const CATEGORY_OPTIONS = [
  { value: "bug", label: "Bug" },
  { value: "data", label: "Data" },
  { value: "billing", label: "Billing" },
  { value: "feature", label: "Feature" },
  { value: "other", label: "Other" },
];

export function AdminBugReports() {
  const { t } = useLang();
  const { can } = useAdmin();

  const { search, setSearch, setFilter } =
    useTableSearch<AdminBugReportsSearch>("/admin/bug-reports");
  const query = search.q ?? "";
  const status = search.status ?? "open";
  const category = search.category ?? "";
  const page = search.page ?? 1;
  const pageSize = search.size ?? 25;
  const setPage = (p: number) => setSearch({ page: p });

  // The open report is addressed by id in the URL, then resolved from the
  // loaded page — so a linked report survives a refresh.
  const openId = search.id ?? null;
  const setOpen = (r: BugReport | null) => setSearch({ id: r?.id ?? undefined });

  const activeFilters = [query, status, category].filter(Boolean).length;
  function clearFilters() {
    setFilter({ q: undefined, status: undefined, category: undefined });
  }

  const summaryQ = useQuery({
    queryKey: ["admin-errors-summary"],
    queryFn: adminApi.errorSummary,
    staleTime: 30_000,
  });

  const q = useQuery({
    queryKey: ["admin-bug-reports", query, status, category, page, pageSize],
    queryFn: () =>
      adminApi.listBugReports({
        query: query || undefined,
        status: status || undefined,
        category: category || undefined,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });

  const columns = useMemo<Column<BugReport>[]>(
    () => [
      {
        id: "title",
        header: t("Report"),
        hideable: false,
        exportValue: (r) => r.title,
        cell: (r) => (
          <div className="min-w-0">
            <div className="truncate font-medium text-text-primary">{r.title}</div>
            <div className="flex items-center gap-1.5">
              <Badge tone="neutral">{r.category}</Badge>
              {r.route && <code className="truncate text-[11px] text-text-muted">{r.route}</code>}
            </div>
          </div>
        ),
      },
      {
        id: "user",
        header: t("Reporter"),
        exportValue: (r) => r.user_email ?? r.user_id,
        cell: (r) => (
          <div className="flex min-w-0 items-center gap-2">
            <Avatar email={r.user_email} size="sm" />
            <Link
              to="/admin/users/$userId"
              params={{ userId: r.user_id }}
              onClick={(e) => e.stopPropagation()}
              className="truncate text-text-secondary hover:text-primary hover:underline"
            >
              {r.user_email ?? r.user_id}
            </Link>
          </div>
        ),
      },
      {
        id: "created_at",
        header: t("Reported"),
        exportValue: (r) => r.created_at,
        cell: (r) => (
          <span className="whitespace-nowrap text-text-muted" title={formatPkt(r.created_at)}>
            {relativeTime(r.created_at)}
          </span>
        ),
      },
      {
        id: "status",
        header: t("Status"),
        exportValue: (r) => r.status,
        cell: (r) => <StatusBadge status={r.status === "wont_fix" ? "ignored" : r.status} />,
      },
      {
        id: "open",
        header: "",
        align: "end",
        hideable: false,
        cell: (r) => (
          <Button size="sm" variant="ghost" onClick={() => setOpen(r)}>
            {t("Open")}
          </Button>
        ),
      },
    ],
    [t],
  );

  if (!can("support.read")) {
    return (
      <Panel>
        <PermissionDenied permission="support.read" />
      </Panel>
    );
  }

  const s = summaryQ.data?.reports;

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Bug Reports")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Bug Reports") }]}
        description={t(
          "Problems users reported themselves. These catch what automatic capture cannot — wrong numbers, confusing flows, and anything that fails without throwing.",
        )}
      />

      {summaryQ.isLoading ? (
        <KpiSkeleton count={3} />
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <KpiCard
            label={t("Open")}
            value={formatNumber(s?.open_reports)}
            icon={<Inbox className="h-4 w-4" />}
            hint={t("Awaiting a first response")}
          />
          <KpiCard
            label={t("Investigating")}
            value={formatNumber(s?.investigating)}
            icon={<MessageSquare className="h-4 w-4" />}
          />
          <KpiCard
            label={t("New this week")}
            value={formatNumber(s?.new_7d)}
            icon={<MessageSquare className="h-4 w-4" />}
            hint={`${formatNumber(s?.total)} ${t("all time")}`}
          />
        </div>
      )}

      <Panel flush>
        <DataTable
          label="Bug reports"
          columns={columns}
          rows={q.data?.items ?? []}
          getRowId={(r) => String(r.id)}
          isLoading={q.isLoading}
          isError={q.isError}
          onRetry={() => void q.refetch()}
          onRowClick={setOpen}
          activeRowId={openId ? String(openId) : null}
          hasFilters={activeFilters > 0}
          onClearFilters={clearFilters}
          emptyState={
            <EmptyBlock
              label={t("No reports")}
              hint={t("Users can file one from the lifebuoy icon in the app header.")}
            />
          }
          toolbar={
            <FilterBar active={activeFilters} onClear={clearFilters}>
              <SearchInput
                value={query}
                onChange={(v) => setFilter({ q: v || undefined }, { replace: true })}
                placeholder={t("Search reports…")}
                className="max-w-xs"
              />
              <FilterSelect
                label={t("Status")}
                allLabel={t("All statuses")}
                value={status}
                onChange={(v) =>
                  setFilter({ status: (v || undefined) as AdminBugReportsSearch["status"] })
                }
                options={STATUS_OPTIONS}
              />
              <FilterSelect
                label={t("Category")}
                allLabel={t("All categories")}
                value={category}
                onChange={(v) =>
                  setFilter({ category: (v || undefined) as AdminBugReportsSearch["category"] })
                }
                options={CATEGORY_OPTIONS}
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

      <ReportDetail
        report={(q.data?.items ?? []).find((r) => r.id === openId) ?? null}
        onClose={() => setOpen(null)}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function ReportDetail({ report, onClose }: { report: BugReport | null; onClose: () => void }) {
  const { t } = useLang();
  const { can } = useAdmin();
  const qc = useQueryClient();
  const [note, setNote] = useState("");

  const mut = useMutation({
    mutationFn: (status: string) =>
      adminApi.triageBugReport(report!.id, status, note.trim() || undefined),
    onSuccess: () => {
      toast.success(t("Report updated"));
      setNote("");
      void qc.invalidateQueries({ queryKey: ["admin-bug-reports"] });
      void qc.invalidateQueries({ queryKey: ["admin-errors-summary"] });
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Drawer
      open={!!report}
      onOpenChange={(v) => !v && onClose()}
      title={report?.title ?? t("Report")}
      description={report?.user_email ?? undefined}
      footer={
        can("support.write") &&
        report && (
          <>
            <Button
              variant="ghost"
              icon={<XCircle className="h-3.5 w-3.5" />}
              loading={mut.isPending}
              onClick={() => mut.mutate("wont_fix")}
            >
              {t("Won't fix")}
            </Button>
            <Button
              variant="secondary"
              loading={mut.isPending}
              onClick={() => mut.mutate("investigating")}
            >
              {t("Investigating")}
            </Button>
            <Button
              variant="primary"
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              loading={mut.isPending}
              onClick={() => mut.mutate("resolved")}
            >
              {t("Resolve")}
            </Button>
          </>
        )
      }
    >
      {report && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={report.status === "wont_fix" ? "ignored" : report.status} />
            <Badge tone="neutral">{report.category}</Badge>
          </div>

          <div>
            <SectionLabel className="mb-1.5">{t("What the user said")}</SectionLabel>
            <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-alt px-3 py-2.5 text-sm text-text-primary">
              {report.description}
            </p>
          </div>

          <div>
            <SectionLabel className="mb-1.5">{t("Context")}</SectionLabel>
            <dl className="rounded-lg border border-border bg-surface-alt px-3 py-1">
              <DataRow
                label={t("Reporter")}
                value={
                  <Link
                    to="/admin/users/$userId"
                    params={{ userId: report.user_id }}
                    onClick={onClose}
                    className="text-primary hover:underline"
                  >
                    {report.user_email ?? report.user_id}
                  </Link>
                }
              />
              <DataRow label={t("Page")} value={report.route ?? "—"} />
              <DataRow label={t("App version")} value={report.app_version ?? "—"} />
              <DataRow label={t("Reported")} value={formatPkt(report.created_at)} />
              {report.error_fingerprint && (
                <DataRow
                  label={t("Linked error")}
                  value={<code className="text-[11px]">{report.error_fingerprint}</code>}
                />
              )}
            </dl>
            {report.user_agent && (
              <p className="mt-1.5 break-all text-[11px] text-text-muted">{report.user_agent}</p>
            )}
          </div>

          {report.admin_note && (
            <div>
              <SectionLabel className="mb-1.5">{t("Current reply")}</SectionLabel>
              <p className="rounded-lg border border-border bg-surface-alt px-3 py-2.5 text-sm text-text-secondary">
                {report.admin_note}
              </p>
            </div>
          )}

          {can("support.write") && (
            <div className="space-y-1.5">
              <label
                htmlFor="report-note"
                className="block text-xs font-medium text-text-secondary"
              >
                {t("Reply to the reporter")}
              </label>
              <Textarea
                id="report-note"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t(
                  "Shown to the user on their report. Saved with the status you pick.",
                )}
              />
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}
