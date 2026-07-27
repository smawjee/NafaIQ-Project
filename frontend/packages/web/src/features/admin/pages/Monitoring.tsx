import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import { adminApi, type MetricBlockLike, type SystemHealth } from "@/features/admin/data/client";
import {
  EmptyBlock,
  ErrorBlock,
  formatPkt,
  LoadingBlock,
  Panel,
  StatCard,
  StatusBadge,
} from "@/features/admin/components/ui";

const TIMESTAMP_KEYS = new Set([
  "last_success",
  "last_error",
  "last_updated",
  "refreshed_at",
  "updated_at",
]);

function renderValue(key: string, value: unknown) {
  if (value == null) return "—";
  if (TIMESTAMP_KEYS.has(key) && typeof value === "string") return formatPkt(value);
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

/** Render one metric block: a list of records, or a flat key/value object. */
function Block({ name, block }: { name: string; block: MetricBlockLike }) {
  const title = name.replace(/_/g, " ");
  if (!block.available) {
    return (
      <Panel title={title}>
        <EmptyBlock label="Unavailable — could not be computed right now." />
      </Panel>
    );
  }
  const items = block.data?.items;
  if (Array.isArray(items)) {
    if (items.length === 0)
      return (
        <Panel title={title}>
          <EmptyBlock />
        </Panel>
      );
    const columns = Array.from(
      items.reduce((set: Set<string>, row) => {
        Object.keys(row as object).forEach((k) => set.add(k));
        return set;
      }, new Set<string>()),
    );
    return (
      <Panel title={title}>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border">
                {columns.map((c) => (
                  <th
                    key={c}
                    className="whitespace-nowrap px-3 py-2 text-start text-xs font-semibold uppercase tracking-wide text-text-muted"
                  >
                    {c.replace(/_/g, " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(items as Record<string, unknown>[]).map((row, i) => (
                <tr key={i} className="border-b border-border/60">
                  {columns.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-2 text-text-primary">
                      {c === "status" ? (
                        <StatusBadge status={String(row[c] ?? "")} />
                      ) : (
                        renderValue(c, row[c])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    );
  }
  const entries = Object.entries(block.data ?? {});
  return (
    <Panel title={title}>
      {entries.length === 0 ? (
        <EmptyBlock />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {entries.map(([k, v]) => (
            <StatCard key={k} label={k.replace(/_/g, " ")} value={renderValue(k, v)} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function MonitoringView({
  title,
  description,
  query,
}: {
  title: string;
  description: string;
  query: UseQueryResult<Record<string, MetricBlockLike>>;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
        <p className="text-sm text-text-muted">{description}</p>
      </div>
      {query.isLoading ? (
        <LoadingBlock />
      ) : query.isError || !query.data ? (
        <ErrorBlock onRetry={() => query.refetch()} />
      ) : (
        Object.entries(query.data).map(([name, block]) => (
          <Block key={name} name={name} block={block} />
        ))
      )}
    </div>
  );
}

export function AdminMarketData() {
  const q = useQuery({
    queryKey: ["admin-market-data"],
    queryFn: adminApi.marketData,
    staleTime: 20_000,
  });
  return (
    <MonitoringView
      title="Market Data"
      description="Health of the PSX ingestion pipeline. Read-only — sourced from psx_data_source_health and the live index snapshot."
      query={q}
    />
  );
}

export function AdminSignals() {
  const q = useQuery({ queryKey: ["admin-signals"], queryFn: adminApi.signals, staleTime: 20_000 });
  return (
    <MonitoringView
      title="Signals"
      description="Signals model registry and computed-table volumes. Read-only monitoring."
      query={q}
    />
  );
}

export function AdminAiOps() {
  const q = useQuery({ queryKey: ["admin-ai"], queryFn: adminApi.aiOps, staleTime: 20_000 });
  return (
    <MonitoringView
      title="AI Operations"
      description="AI usage counts (assistant, LearnHub, reports). No keys or user conversations are exposed."
      query={q}
    />
  );
}

export function AdminSystem() {
  const q = useQuery({ queryKey: ["admin-system"], queryFn: adminApi.system, staleTime: 15_000 });
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">System Health</h1>
        <p className="text-sm text-text-muted">
          Database connectivity and deployment metadata. No secrets, stack traces, or environment
          values are shown.
        </p>
      </div>
      {q.isLoading ? (
        <LoadingBlock />
      ) : q.isError || !q.data ? (
        <ErrorBlock onRetry={() => q.refetch()} />
      ) : (
        <SystemView health={q.data} />
      )}
    </div>
  );
}

function SystemView({ health }: { health: SystemHealth }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Database"
        value={<StatusBadge status={health.database.available ? "success" : "failure"} />}
      />
      <StatCard label="Process role" value={health.deployment.process_role} />
      <StatCard
        label="Scheduler"
        value={health.deployment.scheduler_enabled ? "Enabled" : "Disabled"}
      />
      <StatCard label="Environment" value={health.deployment.environment} />
    </div>
  );
}
