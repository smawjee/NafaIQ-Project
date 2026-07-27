import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/features/admin/data/client";
import {
  EmptyBlock,
  ErrorBlock,
  formatPkt,
  LoadingBlock,
  Panel,
  StatCard,
  StatusBadge,
} from "@/features/admin/components/ui";

function num(v: unknown): string {
  return typeof v === "number" ? v.toLocaleString() : "—";
}

export function AdminOverview() {
  const q = useQuery({
    queryKey: ["admin-overview"],
    queryFn: adminApi.overview,
    staleTime: 30_000,
  });

  if (q.isLoading) return <LoadingBlock />;
  if (q.isError || !q.data) return <ErrorBlock onRetry={() => q.refetch()} />;

  const { users, tiers, engagement, recent_actions } = q.data;
  const u = users.data;
  const e = engagement.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Overview</h1>
        <p className="text-sm text-text-muted">
          Operational snapshot of NafaIQ. All figures are live counts — blocks that can't be
          computed are labelled, never faked.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Total users" value={num(u.total_users)} available={users.available} />
        <StatCard label="New (7d)" value={num(u.new_users_7d)} available={users.available} />
        <StatCard label="Active (7d)" value={num(u.active_users_7d)} available={users.available} />
        <StatCard label="Suspended" value={num(u.suspended_users)} available={users.available} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Subscription tiers" description="Users by plan">
          {!tiers.available ? (
            <EmptyBlock label="Tier data unavailable" />
          ) : (
            <div className="space-y-2">
              {Object.entries(tiers.data).map(([plan, count]) => (
                <div key={plan} className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">{plan}</span>
                  <span className="font-semibold text-text-primary">{num(count)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Engagement" description="Platform-wide totals">
          {!engagement.available ? (
            <EmptyBlock label="Engagement data unavailable" />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <StatCard label="Portfolios" value={num(e.portfolios)} />
              <StatCard label="Watchlist entries" value={num(e.watchlist_entries)} />
              <StatCard label="Price alerts" value={num(e.price_alerts)} />
              <StatCard label="AI reports" value={num(e.ai_reports_total)} />
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Recent admin actions" description="Latest entries from the audit log">
        {recent_actions.length === 0 ? (
          <EmptyBlock label="No admin actions recorded yet" />
        ) : (
          <ul className="divide-y divide-border">
            {recent_actions.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0">
                  <span className="font-medium text-text-primary">{a.action}</span>
                  <span className="ms-2 text-text-muted">{a.actor_email ?? "system"}</span>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <StatusBadge status={a.status} />
                  <span className="text-xs text-text-muted">{formatPkt(a.created_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
