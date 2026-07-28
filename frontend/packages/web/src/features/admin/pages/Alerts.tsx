import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, BellRing, RefreshCw, Send, Users } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import {
  Button,
  CategoryBarChart,
  DataTable,
  EmptyBlock,
  ErrorBlock,
  formatNumber,
  formatPercent,
  KpiCard,
  KpiSkeleton,
  MeterBar,
  PageHeader,
  Panel,
  PanelSkeleton,
  TrendChart,
  type Column,
} from "@/features/admin/components/ui";

interface SymbolRow {
  symbol: string;
  alerts: number;
  users: number;
}

/** Stable empty-object identity so memo deps don't churn while loading. */
const EMPTY: Record<string, never> = {};

export function AdminAlerts() {
  const { t } = useLang();
  const q = useQuery({
    queryKey: ["admin-alerts"],
    queryFn: adminApi.alerts,
    staleTime: 30_000,
  });

  const price = (q.data?.price_alerts.data ?? EMPTY) as Record<string, number>;
  // Memoised: `app` feeds a useMemo below, and a fresh `{}` fallback on every
  // render would invalidate it each time.
  const app = useMemo(
    () => (q.data?.app_alerts.data ?? EMPTY) as Record<string, number>,
    [q.data?.app_alerts.data],
  );
  const delivery = (q.data?.delivery.data ?? EMPTY) as Record<string, number>;

  const trend = (q.data?.events_by_day.data?.items ?? []) as {
    label: string;
    value: number;
  }[];
  const symbols = (q.data?.top_symbols.data?.items ?? []) as SymbolRow[];

  const deliveredPct =
    delivery.events_7d > 0 ? (delivery.delivered / delivery.events_7d) * 100 : null;

  const appTypeBreakdown = useMemo(
    () =>
      (["bill", "budget", "goal", "stock_price"] as const)
        .map((k) => ({ label: k.replace(/_/g, " "), value: app[k] ?? 0 }))
        .filter((d) => d.value > 0),
    [app],
  );

  const symbolColumns = useMemo<Column<SymbolRow>[]>(
    () => [
      {
        id: "symbol",
        header: "Symbol",
        hideable: false,
        exportValue: (r) => r.symbol,
        cell: (r) => <span className="font-medium text-text-primary">{r.symbol}</span>,
      },
      {
        id: "alerts",
        header: "Active alerts",
        align: "end",
        exportValue: (r) => r.alerts,
        cell: (r) => <span className="tabular">{formatNumber(r.alerts)}</span>,
      },
      {
        id: "users",
        header: "Distinct users",
        align: "end",
        exportValue: (r) => r.users,
        cell: (r) => <span className="tabular text-text-secondary">{formatNumber(r.users)}</span>,
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Alerts")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Alerts") }]}
        description="Platform-wide alert volume and delivery health. Aggregates only — the contents of an individual user's alerts are never exposed to this console."
        actions={
          <Button
            variant="outline"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            loading={q.isFetching}
            onClick={() => void q.refetch()}
          >
            Refresh
          </Button>
        }
      />

      {q.isLoading ? (
        <div className="space-y-4">
          <KpiSkeleton />
          <Panel>
            <PanelSkeleton lines={6} />
          </Panel>
        </div>
      ) : q.isError || !q.data ? (
        <Panel>
          <ErrorBlock onRetry={() => void q.refetch()} />
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KpiCard
              label="Price alerts"
              value={formatNumber(price.enabled)}
              available={q.data.price_alerts.available}
              icon={<Bell className="h-4 w-4" />}
              hint={`${formatNumber(price.total)} total, ${formatNumber(price.symbols_watched)} symbols`}
            />
            <KpiCard
              label="App alerts"
              value={formatNumber(app.enabled)}
              available={q.data.app_alerts.available}
              icon={<BellRing className="h-4 w-4" />}
              hint={`${formatNumber(app.total)} total across bill, budget & goal`}
            />
            <KpiCard
              label="Fired (24h)"
              value={formatNumber(price.triggered_24h)}
              available={q.data.price_alerts.available}
              icon={<Send className="h-4 w-4" />}
              hint="Price alerts triggered in the last day"
            />
            <KpiCard
              label="Users with alerts"
              value={formatNumber(price.users_with_alerts)}
              available={q.data.price_alerts.available}
              icon={<Users className="h-4 w-4" />}
              hint="Distinct users holding a price alert"
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Panel
              title="Delivery health"
              description="Alert events raised in the last 7 days"
              className="xl:col-span-1"
            >
              {!q.data.delivery.available ? (
                <EmptyBlock label="Delivery data unavailable" />
              ) : delivery.events_7d === 0 ? (
                <EmptyBlock
                  label="No alert events in the last 7 days"
                  hint="Either no alerts met their conditions, or the evaluator isn't running."
                />
              ) : (
                <div className="space-y-4">
                  <div>
                    <div className="mb-1.5 flex items-baseline justify-between">
                      <span className="text-xs text-text-muted">Delivered</span>
                      <span className="tabular text-sm font-semibold text-text-primary">
                        {formatPercent(deliveredPct)}
                      </span>
                    </div>
                    <MeterBar
                      segments={[
                        { label: "Delivered", value: delivery.delivered, className: "bg-bull" },
                        {
                          label: "Undelivered",
                          value: delivery.undelivered,
                          className: "bg-bear",
                        },
                      ]}
                    />
                    <p className="mt-1.5 text-[11px] text-text-muted">
                      {formatNumber(delivery.delivered)} delivered ·{" "}
                      {formatNumber(delivery.undelivered)} undelivered ·{" "}
                      {formatNumber(delivery.read)} read
                    </p>
                  </div>

                  <div className="border-t border-border pt-3">
                    <div className="mb-2 text-xs text-text-muted">By channel</div>
                    <dl className="space-y-1.5 text-sm">
                      {(
                        [
                          ["In-app", delivery.via_in_app],
                          ["Email", delivery.via_email],
                          ["Push", delivery.via_push],
                        ] as const
                      ).map(([label, value]) => (
                        <div key={label} className="flex items-center justify-between">
                          <dt className="text-text-secondary">{label}</dt>
                          <dd className="tabular font-medium text-text-primary">
                            {formatNumber(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </div>
              )}
            </Panel>

            <Panel
              title="Alert events"
              description="Daily volume over the last 14 days (PKT)"
              className="xl:col-span-2"
            >
              {!q.data.events_by_day.available ? (
                <EmptyBlock label="Event history unavailable" />
              ) : (
                <TrendChart data={trend} name="Events" height={240} />
              )}
            </Panel>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="App alerts by type" description="Enabled and disabled combined">
              {!q.data.app_alerts.available ? (
                <EmptyBlock label="App alert data unavailable" />
              ) : appTypeBreakdown.length === 0 ? (
                <EmptyBlock label="No app alerts have been created yet" />
              ) : (
                <CategoryBarChart data={appTypeBreakdown} name="Alerts" height={240} />
              )}
            </Panel>

            <Panel title="Most-watched symbols" description="Across all enabled price alerts" flush>
              {!q.data.top_symbols.available ? (
                <EmptyBlock label="Symbol data unavailable" />
              ) : (
                <DataTable
                  label="Most-watched symbols"
                  columns={symbolColumns}
                  rows={symbols}
                  getRowId={(r) => r.symbol}
                  enableColumnControl={false}
                  emptyState={<EmptyBlock label="No active price alerts" />}
                />
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
