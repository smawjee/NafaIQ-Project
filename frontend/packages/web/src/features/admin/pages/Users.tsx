import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { adminApi } from "@/features/admin/data/client";
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

const PAGE_SIZE = 25;

export function AdminUsers() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);

  // Debounce the search box so each keystroke doesn't fire a request.
  function onSearch(v: string) {
    setQuery(v);
    window.clearTimeout((onSearch as unknown as { t?: number }).t);
    (onSearch as unknown as { t?: number }).t = window.setTimeout(() => {
      setDebounced(v);
      setPage(1);
    }, 300);
  }

  const q = useQuery({
    queryKey: ["admin-users", debounced, status, plan, page],
    queryFn: () =>
      adminApi.listUsers({
        query: debounced || undefined,
        status: status || undefined,
        plan: plan || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Users</h1>
        <p className="text-sm text-text-muted">Search, inspect, and manage user accounts.</p>
      </div>

      <Panel>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute start-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <input
              value={query}
              onChange={(e) => onSearch(e.target.value)}
              placeholder="Search by email or name…"
              className="w-full rounded-lg border border-border bg-background py-2 ps-9 pe-3 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
            />
          </div>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:border-primary focus:outline-none"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="restricted">Restricted</option>
          </select>
          <select
            value={plan}
            onChange={(e) => {
              setPlan(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:border-primary focus:outline-none"
          >
            <option value="">All plans</option>
            <option value="Free">Free</option>
            <option value="Pro">Pro</option>
            <option value="Premium">Premium</option>
          </select>
        </div>

        {q.isLoading ? (
          <LoadingBlock />
        ) : q.isError || !q.data ? (
          <ErrorBlock onRetry={() => q.refetch()} />
        ) : q.data.items.length === 0 ? (
          <EmptyBlock label="No users match those filters." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <Th>Email</Th>
                    <Th>Name</Th>
                    <Th>Plan</Th>
                    <Th>Status</Th>
                    <Th>Joined</Th>
                    <Th>Last seen</Th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.items.map((u) => (
                    <tr key={u.id} className="border-b border-border/60 hover:bg-hover">
                      <Td>
                        <Link
                          to="/admin/users/$userId"
                          params={{ userId: u.id }}
                          className="font-medium text-primary hover:underline"
                        >
                          {u.email ?? u.id}
                        </Link>
                      </Td>
                      <Td className="text-text-secondary">{u.display_name ?? "—"}</Td>
                      <Td>{u.plan}</Td>
                      <Td>
                        <StatusBadge status={u.account_status} />
                      </Td>
                      <Td className="text-text-muted">{formatPkt(u.created_at, false)}</Td>
                      <Td className="text-text-muted">{formatPkt(u.last_sign_in_at)}</Td>
                    </tr>
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
