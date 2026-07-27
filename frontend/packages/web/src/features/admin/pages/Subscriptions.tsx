import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { adminApi } from "@/features/admin/data/client";
import {
  EmptyBlock,
  ErrorBlock,
  LoadingBlock,
  Panel,
  StatCard,
} from "@/features/admin/components/ui";

function num(v: unknown): string {
  return typeof v === "number" ? v.toLocaleString() : "—";
}

export function AdminSubscriptions() {
  const q = useQuery({
    queryKey: ["admin-overview"],
    queryFn: adminApi.overview,
    staleTime: 30_000,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Subscriptions</h1>
        <p className="text-sm text-text-muted">
          Tier distribution across the user base. Change an individual user's tier from their
          profile. Payment-provider integration is a future extension — tiers are currently assigned
          manually.
        </p>
      </div>

      {q.isLoading ? (
        <LoadingBlock />
      ) : q.isError || !q.data ? (
        <ErrorBlock onRetry={() => q.refetch()} />
      ) : !q.data.tiers.available ? (
        <EmptyBlock label="Tier data unavailable" />
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {Object.entries(q.data.tiers.data).map(([plan, count]) => (
            <StatCard key={plan} label={`${plan} plan`} value={num(count)} />
          ))}
        </div>
      )}

      <Panel title="Manage a user's tier">
        <p className="text-sm text-text-secondary">
          Open a user from the{" "}
          <Link to="/admin/users" className="text-primary hover:underline">
            Users
          </Link>{" "}
          page to change their subscription tier. Every change is recorded in the audit log with the
          acting admin and the before/after tier.
        </p>
      </Panel>
    </div>
  );
}
