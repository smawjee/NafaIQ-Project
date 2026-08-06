import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { Activity, Database, RefreshCw, Server, Timer } from "lucide-react";
import { toast } from "sonner";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { adminApi, type MetricBlockLike, type SystemHealth } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import {
  Badge,
  Button,
  CategoryBarChart,
  DataTable,
  EmptyBlock,
  ErrorBlock,
  formatCompact,
  formatNumber,
  formatPkt,
  humanizeKey,
  KpiCard,
  KpiSkeleton,
  PageHeader,
  Panel,
  PanelSkeleton,
  relativeTime,
  StatusBadge,
  type Column,
} from "@/features/admin/components/ui";

/** Keys whose values are timestamps rather than plain scalars. */
const TIMESTAMP_KEYS = new Set([
  "last_success",
  "last_error",
  "last_updated",
  "refreshed_at",
  "updated_at",
  "as_of",
]);

function renderValue(key: string, value: unknown) {
  if (value == null) return "—";
  if (TIMESTAMP_KEYS.has(key) && typeof value === "string") return formatPkt(value);
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

/* -------------------------------------------------------------------------- */
/* Generic metric block renderer                                               */
/* -------------------------------------------------------------------------- */

type Row = Record<string, unknown>;

/**
 * A metric block is either a list of records (`data.items`) or a flat
 * key/value object. Lists render through the shared DataTable so monitoring
 * inherits sorting, column control and CSV export like every other screen.
 */
function Block({ name, block }: { name: string; block: MetricBlockLike }) {
  const title = humanizeKey(name);
  const items = block.data?.items;
  const isList = Array.isArray(items);

  const columns = useMemo<Column<Row>[]>(() => {
    if (!isList) return [];
    const keys = Array.from(
      (items as Row[]).reduce((set: Set<string>, row) => {
        Object.keys(row ?? {}).forEach((k) => set.add(k));
        return set;
      }, new Set<string>()),
    );
    return keys.map((k, i) => ({
      id: k,
      header: humanizeKey(k),
      hideable: i > 0,
      exportValue: (r) => r[k],
      cell: (r) =>
        k === "status" ? (
          <StatusBadge status={String(r[k] ?? "")} />
        ) : TIMESTAMP_KEYS.has(k) ? (
          <span className="whitespace-nowrap text-text-muted" title={formatPkt(r[k] as string)}>
            {relativeTime(r[k] as string)}
          </span>
        ) : (
          <span className={typeof r[k] === "number" ? "tabular" : undefined}>
            {renderValue(k, r[k])}
          </span>
        ),
    }));
  }, [isList, items]);

  if (!block.available) {
    return (
      <Panel title={title}>
        <EmptyBlock
          label="Unavailable"
          hint="This metric couldn't be computed on the last request. It is not a zero — the query failed."
        />
      </Panel>
    );
  }

  if (isList) {
    const rows = items as Row[];
    return (
      <Panel title={title} flush>
        <DataTable
          label={title}
          columns={columns}
          rows={rows}
          getRowId={(r) => String(r.id ?? r.symbol ?? r.name ?? r.source ?? JSON.stringify(r))}
          emptyState={<EmptyBlock label="No records" />}
        />
      </Panel>
    );
  }

  const entries = Object.entries(block.data ?? {});
  if (entries.length === 0) {
    return (
      <Panel title={title}>
        <EmptyBlock label="No data" />
      </Panel>
    );
  }

  // Numeric-only blocks get a chart alongside the tiles — it turns a wall of
  // figures into a comparison at a glance.
  const numeric = entries.filter(([, v]) => typeof v === "number") as [string, number][];
  const showChart = numeric.length >= 3 && numeric.length === entries.length;

  return (
    <Panel title={title}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {entries.map(([k, v]) => (
          <div
            key={k}
            className="rounded-lg border border-border bg-surface-alt p-3 transition-colors hover:border-border-hover"
          >
            <div className="text-[11px] text-text-muted">{humanizeKey(k)}</div>
            <div
              className="tabular mt-1 truncate text-lg font-semibold text-text-primary"
              title={String(v ?? "")}
            >
              {typeof v === "number" ? formatCompact(v) : renderValue(k, v)}
            </div>
          </div>
        ))}
      </div>
      {showChart && (
        <div className="mt-4 border-t border-border pt-4">
          <CategoryBarChart
            data={numeric.map(([label, value]) => ({ label: humanizeKey(label), value }))}
            height={200}
          />
        </div>
      )}
    </Panel>
  );
}

function MonitoringView({
  title,
  description,
  breadcrumb,
  query,
  actions,
}: {
  title: string;
  description: string;
  breadcrumb: string;
  query: UseQueryResult<Record<string, MetricBlockLike>>;
  actions?: React.ReactNode;
}) {
  const { t } = useLang();
  return (
    <div className="space-y-5">
      <PageHeader
        title={t(title)}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t(breadcrumb) }]}
        description={description}
        actions={
          <>
            {actions}
            <Button
              variant="outline"
              icon={<RefreshCw className="h-3.5 w-3.5" />}
              loading={query.isFetching}
              onClick={() => void query.refetch()}
            >
              Refresh
            </Button>
          </>
        }
      />
      {query.isLoading ? (
        <div className="space-y-4">
          <KpiSkeleton />
          <Panel>
            <PanelSkeleton lines={6} />
          </Panel>
        </div>
      ) : query.isError || !query.data ? (
        <Panel>
          <ErrorBlock onRetry={() => void query.refetch()} />
        </Panel>
      ) : (
        <div className="space-y-4">
          {Object.entries(query.data).map(([name, block]) => (
            <Block key={name} name={name} block={block} />
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Pages                                                                       */
/* -------------------------------------------------------------------------- */

export function AdminMarketData() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { can } = useAdmin();

  const q = useQuery({
    queryKey: ["admin-market-data"],
    queryFn: adminApi.marketData,
    staleTime: 20_000,
  });

  // Real operational action: asks the backend to re-run the market snapshot
  // scrape immediately rather than waiting for the 10s cron tick.
  const refreshMut = useMutation({
    mutationFn: () => adminApi.refreshMarketData(),
    onSuccess: (r) => {
      toast.success(r?.detail ?? "Market data refresh triggered");
      void qc.invalidateQueries({ queryKey: ["admin-market-data"] });
      void qc.invalidateQueries({ queryKey: ["admin-audit"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <MonitoringView
      title="Market Data"
      breadcrumb="Market Data"
      description="Health of the PSX ingestion pipeline — per-source status, the live index snapshot and the market snapshot table."
      query={q}
      actions={
        can("market_data.refresh") && (
          <Button
            variant="primary"
            icon={<Database className="h-3.5 w-3.5" />}
            loading={refreshMut.isPending}
            onClick={() =>
              confirm({
                title: "Trigger a market-data refresh?",
                description:
                  "Runs the market snapshot scrape immediately instead of waiting for the next scheduled tick. Safe to run at any time; the action is recorded in the audit log.",
                confirmText: "Refresh now",
                onConfirm: async () => {
                  await refreshMut.mutateAsync();
                },
              })
            }
          >
            Refresh now
          </Button>
        )
      }
    />
  );
}

export function AdminSignals() {
  const q = useQuery({ queryKey: ["admin-signals"], queryFn: adminApi.signals, staleTime: 20_000 });
  return (
    <MonitoringView
      title="Signals"
      breadcrumb="Signals"
      description="Signals model registry and computed-table volumes. Read-only — the serving path is /api/signals."
      query={q}
    />
  );
}

export function AdminAiOps() {
  const q = useQuery({ queryKey: ["admin-ai"], queryFn: adminApi.aiOps, staleTime: 20_000 });
  return (
    <MonitoringView
      title="AI Operations"
      breadcrumb="AI Operations"
      description="Usage counts for the assistant, LearnHub and report generators. No API keys, prompts or user conversations are exposed here."
      query={q}
    />
  );
}

/* -------------------------------------------------------------------------- */

export function AdminSystem() {
  const { t } = useLang();
  const q = useQuery({ queryKey: ["admin-system"], queryFn: adminApi.system, staleTime: 15_000 });

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("System Health")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("System Health") }]}
        description="Database connectivity and deployment metadata. No secrets, stack traces or environment values are ever returned by this endpoint."
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
        <KpiSkeleton />
      ) : q.isError || !q.data ? (
        <Panel>
          <ErrorBlock onRetry={() => void q.refetch()} />
        </Panel>
      ) : (
        <SystemView health={q.data} />
      )}
    </div>
  );
}

function SystemView({ health }: { health: SystemHealth }) {
  const dbOk = health.database.available;
  return (
    <div className="space-y-4">
      <div
        className={`rounded-xl border px-4 py-3 text-sm ${
          dbOk ? "border-bull/30 bg-bull/10 text-bull" : "border-bear/30 bg-bear/10 text-bear"
        }`}
      >
        <span className="font-medium">
          {dbOk ? "All monitored systems are responding." : "Database is not reachable."}
        </span>
        {!dbOk && " Ingestion, signals and every user-facing query will be failing."}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Database"
          value={<StatusBadge status={dbOk ? "healthy" : "down"} />}
          icon={<Database className="h-4 w-4" />}
          hint="Supabase transaction pooler"
        />
        <KpiCard
          label="Process role"
          value={health.deployment.process_role}
          icon={<Server className="h-4 w-4" />}
          hint="PROCESS_ROLE"
        />
        <KpiCard
          label="Scheduler"
          value={
            <StatusBadge status={health.deployment.scheduler_enabled ? "enabled" : "suspended"} />
          }
          icon={<Timer className="h-4 w-4" />}
          hint={
            health.deployment.scheduler_enabled
              ? "Cron jobs running on this process"
              : "This process does not run jobs"
          }
        />
        <KpiCard
          label="Environment"
          value={<Badge tone="accent">{health.deployment.environment}</Badge>}
          icon={<Activity className="h-4 w-4" />}
          hint="Derived from CORS config"
        />
      </div>

      <Panel
        title="What this page does not cover"
        description="Being explicit about monitoring gaps is more useful than implying full coverage."
      >
        <ul className="space-y-1.5 text-sm text-text-secondary">
          <li>• Per-job scheduler run history — jobs report into Market Data, not here.</li>
          <li>• Upstream provider health (Gemini, Groq) — see AI Operations for usage volume.</li>
          <li>• Application error rates — no error-tracking sink is wired to this console yet.</li>
        </ul>
      </Panel>
    </div>
  );
}
