import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { FlagInfo } from "@/features/admin/data/types";
import { Badge, ErrorBlock, formatPkt, LoadingBlock, Panel } from "@/features/admin/components/ui";

export function AdminFlags() {
  const qc = useQueryClient();
  const { can } = useAdmin();
  const canWrite = can("flags.write");

  const q = useQuery({ queryKey: ["admin-flags"], queryFn: adminApi.listFlags, staleTime: 30_000 });

  const mut = useMutation({
    mutationFn: (v: { key: string; value: unknown; enabled?: boolean }) =>
      adminApi.updateFlag(v.key, v.value, v.enabled),
    onSuccess: () => {
      toast.success("Flag updated");
      qc.invalidateQueries({ queryKey: ["admin-flags"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Feature Flags</h1>
        <p className="text-sm text-text-muted">
          Typed, validated platform switches. Changes are audited. These control server-side
          behaviour without a redeploy.
        </p>
      </div>

      {q.isLoading ? (
        <LoadingBlock />
      ) : q.isError || !q.data ? (
        <ErrorBlock onRetry={() => q.refetch()} />
      ) : (
        <div className="space-y-3">
          {q.data.map((flag) => (
            <FlagCard
              key={flag.key}
              flag={flag}
              canWrite={canWrite}
              saving={mut.isPending}
              onChange={(value) => mut.mutate({ key: flag.key, value })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FlagCard({
  flag,
  canWrite,
  saving,
  onChange,
}: {
  flag: FlagInfo;
  canWrite: boolean;
  saving: boolean;
  onChange: (value: unknown) => void;
}) {
  return (
    <Panel>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-text-primary">{flag.key}</span>
            <Badge>{flag.type}</Badge>
          </div>
          {flag.description && <p className="mt-0.5 text-xs text-text-muted">{flag.description}</p>}
          <p className="mt-1 text-[11px] text-text-muted">Updated {formatPkt(flag.updated_at)}</p>
        </div>
        <div className="shrink-0">
          {flag.type === "bool" ? (
            <button
              disabled={!canWrite || saving}
              onClick={() => onChange(!flag.value)}
              className={
                "relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 " +
                (flag.value ? "bg-bull" : "bg-muted")
              }
              aria-pressed={!!flag.value}
              aria-label={`Toggle ${flag.key}`}
            >
              <span
                className={
                  "inline-block h-5 w-5 transform rounded-full bg-white transition-transform " +
                  (flag.value ? "translate-x-5" : "translate-x-1")
                }
              />
            </button>
          ) : (
            <span className="rounded-md border border-border bg-muted px-2 py-1 font-mono text-xs text-text-secondary">
              {JSON.stringify(flag.value)}
            </span>
          )}
        </div>
      </div>
    </Panel>
  );
}
