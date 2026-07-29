import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Bot,
  Briefcase,
  Eye,
  RefreshCw,
  ShieldAlert,
  UserPlus,
  Users as UsersIcon,
} from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { AuditEntry, TelemetrySummary } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  Button,
  DonutChart,
  EmptyBlock,
  ErrorBlock,
  formatCompact,
  formatNumber,
  humanizeAction,
  KpiCard,
  KpiSkeleton,
  PageHeader,
  Panel,
  PanelSkeleton,
  relativeTime,
  StatusBadge,
} from "@/features/admin/components/ui";

/** Engagement rows are keyed by the metrics repo; labels/icons are mapped here. */
const ENGAGEMENT_ROWS: { key: string; label: string; icon: typeof Briefcase }[] = [
  { key: "portfolios", label: "Portfolios", icon: Briefcase },
  { key: "watchlist_entries", label: "Watchlist entries", icon: Eye },
  { key: "price_alerts", label: "Price alerts", icon: Bell },
  { key: "app_alerts", label: "App alerts", icon: Bell },
  { key: "ai_reports_total", label: "AI reports", icon: Bot },
  { key: "assistant_events_total", label: "Assistant events", icon: Bot },
];

export function AdminOverview() {
  const { t } = useLang();
  const { can } = useAdmin();
  const q = useQuery({
    queryKey: ["admin-overview"],
    queryFn: adminApi.overview,
    staleTime: 30_000,
  });

  // Reliability belongs on the landing screen. An admin who has to navigate to
  // /admin/errors to discover an overnight crash will find out from a user
  // first — which defeats the point of capturing anything.
  const relQ = useQuery({
    queryKey: ["admin-errors-summary"],
    queryFn: adminApi.errorSummary,
    enabled: can("errors.read") || can("support.read"),
    staleTime: 30_000,
  });

  const users = q.data?.users;
  const tiers = q.data?.tiers;
  const engagement = q.data?.engagement;
  const u = (users?.data ?? {}) as Record<string, number>;

  const tierSegments = Object.entries(tiers?.data ?? {}).map(([label, value]) => ({
    label,
    value: Number(value) || 0,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Dashboard")}
        description="Live operational snapshot. Every figure is a real count — a block that can't be computed is labelled, never estimated or faked."
        actions={
          <Button
            variant="outline"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={() => void q.refetch()}
            loading={q.isFetching}
          >
            Refresh
          </Button>
        }
      />

      {q.isLoading ? (
        <KpiSkeleton />
      ) : q.isError ? (
        <Panel>
          <ErrorBlock onRetry={() => void q.refetch()} />
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard
              label="Total users"
              value={formatNumber(u.total_users)}
              available={users?.available}
              icon={<UsersIcon className="h-4 w-4" />}
              hint={`${formatNumber(u.new_users_30d)} joined in 30d`}
            />
            <KpiCard
              label="New this week"
              value={formatNumber(u.new_users_7d)}
              available={users?.available}
              icon={<UserPlus className="h-4 w-4" />}
              hint="Sign-ups in the last 7 days"
            />
            <KpiCard
              label="Active this week"
              value={formatNumber(u.active_users_7d)}
              available={users?.available}
              icon={<Activity className="h-4 w-4" />}
              hint={
                users?.available && u.total_users
                  ? `${Math.round((u.active_users_7d / u.total_users) * 100)}% of base`
                  : undefined
              }
            />
            <KpiCard
              label="Suspended"
              value={formatNumber(u.suspended_users)}
              available={users?.available}
              icon={<ShieldAlert className="h-4 w-4" />}
              hint="Blocked from authenticated actions"
            />
          </div>

          {(can("errors.read") || can("support.read")) && <ReliabilityStrip data={relQ.data} />}

          <div className="grid gap-4">
            <Panel
              title="Subscription tiers"
              description="Distribution across the whole user base"
              actions={
                can("users.tier.read") && (
                  <Link
                    to="/admin/subscriptions"
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    Manage <ArrowUpRight className="h-3 w-3" aria-hidden />
                  </Link>
                )
              }
            >
              {!tiers?.available ? (
                <EmptyBlock
                  label="Tier data unavailable"
                  hint="The aggregate query failed on this request."
                />
              ) : (
                <DonutChart data={tierSegments} height={220} centerLabel="users" />
              )}
            </Panel>

            <Panel
              title="Platform engagement"
              description="Lifetime totals across user-owned records"
            >
              {!engagement?.available ? (
                <EmptyBlock label="Engagement data unavailable" />
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {ENGAGEMENT_ROWS.map((row) => {
                    const value = (engagement.data as Record<string, unknown>)[row.key];
                    if (typeof value !== "number") return null;
                    return (
                      <div
                        key={row.key}
                        className="rounded-lg border border-border bg-surface-alt p-3 transition-colors hover:border-border-hover"
                      >
                        <div className="flex items-center gap-1.5 text-xs text-text-muted">
                          <row.icon className="h-3.5 w-3.5" aria-hidden />
                          {row.label}
                        </div>
                        <div
                          className="tabular mt-1.5 text-xl font-semibold text-text-primary"
                          title={formatNumber(value)}
                        >
                          {formatCompact(value)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Panel>
          </div>

          <Panel
            title="Recent admin activity"
            description="Latest entries from the append-only audit log"
            flush
            actions={
              can("audit.read") && (
                <Link
                  to="/admin/audit"
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  Full log <ArrowUpRight className="h-3 w-3" aria-hidden />
                </Link>
              )
            }
          >
            {q.data!.recent_actions.length === 0 ? (
              <EmptyBlock
                label="No admin actions recorded yet"
                hint="Suspensions, tier changes, role grants and flag edits all appear here."
              />
            ) : (
              <ul className="divide-y divide-border">
                {q.data!.recent_actions.map((a) => (
                  <ActivityRow key={a.id} entry={a} />
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}

      {q.isLoading && (
        <Panel title="Recent admin activity">
          <PanelSkeleton lines={5} />
        </Panel>
      )}
    </div>
  );
}

function ActivityRow({ entry }: { entry: AuditEntry }) {
  return (
    <li className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-hover">
      <Avatar email={entry.actor_email} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm text-text-primary">
          <span className="font-medium">{humanizeAction(entry.action)}</span>
          {entry.resource_type && (
            <Badge className="ms-2" tone="neutral">
              {entry.resource_type}
            </Badge>
          )}
        </div>
        <div className="truncate text-xs text-text-muted">{entry.actor_email ?? "system"}</div>
      </div>
      <StatusBadge status={entry.status} />
      <span className="hidden shrink-0 text-xs text-text-muted sm:block" title={entry.created_at}>
        {relativeTime(entry.created_at)}
      </span>
    </li>
  );
}

/**
 * Reliability banner.
 *
 * Deliberately silent when everything is healthy — a permanent green bar teaches
 * admins to ignore the whole strip, so it only appears when there is something
 * to act on, and links straight to the queue that owns it.
 */
function ReliabilityStrip({ data }: { data?: TelemetrySummary }) {
  const { t } = useLang();
  const { can } = useAdmin();
  if (!data) return null;

  const openErrors = data.errors?.open_groups ?? 0;
  const activeErrors = data.errors?.active_24h ?? 0;
  const openReports = data.reports?.open_reports ?? 0;
  if (openErrors === 0 && openReports === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3">
      <ShieldAlert className="h-4 w-4 shrink-0 text-warning" aria-hidden />
      <div className="min-w-0 flex-1 text-sm text-warning">
        {openErrors > 0 && (
          <span>
            <span className="tabular font-semibold">{formatNumber(openErrors)}</span>{" "}
            {openErrors === 1 ? t("unresolved error") : t("unresolved errors")}
            {activeErrors > 0 && (
              <span className="opacity-80">
                {" "}
                ({formatNumber(activeErrors)} {t("active today")})
              </span>
            )}
          </span>
        )}
        {openErrors > 0 && openReports > 0 && <span className="mx-2 opacity-50">·</span>}
        {openReports > 0 && (
          <span>
            <span className="tabular font-semibold">{formatNumber(openReports)}</span>{" "}
            {openReports === 1 ? t("user report awaiting reply") : t("user reports awaiting reply")}
          </span>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {openErrors > 0 && can("errors.read") && (
          <Link
            to="/admin/errors"
            className="inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
          >
            {t("Errors")} <ArrowUpRight className="h-3 w-3" aria-hidden />
          </Link>
        )}
        {openReports > 0 && can("support.read") && (
          <Link
            to="/admin/bug-reports"
            className="inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
          >
            {t("Bug Reports")} <ArrowUpRight className="h-3 w-3" aria-hidden />
          </Link>
        )}
      </div>
    </div>
  );
}
