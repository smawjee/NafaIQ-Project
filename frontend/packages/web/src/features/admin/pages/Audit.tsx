import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { adminApi } from "@/features/admin/data/client";
import type { AuditEntry } from "@/features/admin/data/types";
import {
  EmptyBlock,
  ErrorBlock,
  formatPkt,
  LoadingBlock,
  Pagination,
  Panel,
  StatusBadge,
  Td,
  Th,
} from "@/features/admin/components/ui";

const PAGE_SIZE = 50;

export function AdminAudit() {
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);

  const q = useQuery({
    queryKey: ["admin-audit", action, status, page],
    queryFn: () =>
      adminApi.listAudit({
        action: action || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
    staleTime: 10_000,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Audit Log</h1>
        <p className="text-sm text-text-muted">
          Every administrative action, append-only and immutable. Times shown in PKT.
        </p>
      </div>

      <Panel>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <input
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
            placeholder="Filter by action (e.g. admin.user.tier)"
            className="min-w-[220px] flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
          />
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:border-primary focus:outline-none"
          >
            <option value="">All</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
          </select>
        </div>

        {q.isLoading ? (
          <LoadingBlock />
        ) : q.isError || !q.data ? (
          <ErrorBlock onRetry={() => q.refetch()} />
        ) : q.data.items.length === 0 ? (
          <EmptyBlock label="No audit entries match those filters." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <Th>When</Th>
                    <Th>Actor</Th>
                    <Th>Action</Th>
                    <Th>Resource</Th>
                    <Th>Status</Th>
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {q.data.items.map((a) => (
                    <AuditRow
                      key={a.id}
                      entry={a}
                      open={expanded === a.id}
                      onToggle={() => setExpanded(expanded === a.id ? null : a.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={q.data.meta.page}
              pageSize={q.data.meta.page_size}
              total={q.data.meta.total}
              onPage={setPage}
            />
          </>
        )}
      </Panel>
    </div>
  );
}

function AuditRow({
  entry,
  open,
  onToggle,
}: {
  entry: AuditEntry;
  open: boolean;
  onToggle: () => void;
}) {
  const hasDetail = entry.before != null || entry.after != null || entry.reason;
  return (
    <>
      <tr className="border-b border-border/60 hover:bg-hover">
        <Td className="whitespace-nowrap text-text-muted">{formatPkt(entry.created_at)}</Td>
        <Td>{entry.actor_email ?? "system"}</Td>
        <Td className="font-medium">{entry.action}</Td>
        <Td className="text-text-secondary">
          {entry.resource_type
            ? `${entry.resource_type}${entry.resource_id ? `:${entry.resource_id}` : ""}`
            : "—"}
        </Td>
        <Td>
          <StatusBadge status={entry.status} />
        </Td>
        <Td>
          {hasDetail && (
            <button onClick={onToggle} className="text-xs text-primary hover:underline">
              {open ? "Hide" : "Details"}
            </button>
          )}
        </Td>
      </tr>
      {open && hasDetail && (
        <tr className="border-b border-border/60 bg-background/60">
          <td colSpan={6} className="px-3 py-2">
            <div className="grid gap-2 text-xs sm:grid-cols-2">
              {entry.reason && (
                <div className="sm:col-span-2">
                  <span className="text-text-muted">Reason: </span>
                  <span className="text-text-primary">{entry.reason}</span>
                </div>
              )}
              {entry.before != null && (
                <pre className="overflow-x-auto rounded-md border border-border bg-card p-2 text-text-secondary">
                  before: {JSON.stringify(entry.before, null, 2)}
                </pre>
              )}
              {entry.after != null && (
                <pre className="overflow-x-auto rounded-md border border-border bg-card p-2 text-text-secondary">
                  after: {JSON.stringify(entry.after, null, 2)}
                </pre>
              )}
              {entry.request_id && (
                <div className="text-text-muted">request_id: {entry.request_id}</div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
