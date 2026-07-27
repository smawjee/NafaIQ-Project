import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/features/admin/data/client";
import {
  Badge,
  EmptyBlock,
  ErrorBlock,
  formatPkt,
  LoadingBlock,
  Panel,
  Td,
  Th,
} from "@/features/admin/components/ui";

export function AdminRoles() {
  const rolesQ = useQuery({
    queryKey: ["admin-roles-list"],
    queryFn: adminApi.listRoles,
    staleTime: 5 * 60_000,
  });
  const adminsQ = useQuery({
    queryKey: ["admin-admins"],
    queryFn: adminApi.listAdmins,
    staleTime: 30_000,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Roles &amp; Access</h1>
        <p className="text-sm text-text-muted">
          Roles are fixed and permission-mapped in the database. Grant or revoke a user's roles from
          their profile page.
        </p>
      </div>

      <Panel title="Current admins">
        {adminsQ.isLoading ? (
          <LoadingBlock />
        ) : adminsQ.isError || !adminsQ.data ? (
          <ErrorBlock onRetry={() => adminsQ.refetch()} />
        ) : adminsQ.data.length === 0 ? (
          <EmptyBlock label="No admins found." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <Th>Email</Th>
                  <Th>Roles</Th>
                  <Th>Since</Th>
                </tr>
              </thead>
              <tbody>
                {adminsQ.data.map((a) => (
                  <tr key={a.user_id} className="border-b border-border/60">
                    <Td>{a.email ?? a.user_id}</Td>
                    <Td>
                      <div className="flex flex-wrap gap-1">
                        {a.roles.map((r) => (
                          <Badge key={r}>{r}</Badge>
                        ))}
                      </div>
                    </Td>
                    <Td className="text-text-muted">{formatPkt(a.first_granted_at, false)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Roles &amp; permissions">
        {rolesQ.isLoading ? (
          <LoadingBlock />
        ) : rolesQ.isError || !rolesQ.data ? (
          <ErrorBlock onRetry={() => rolesQ.refetch()} />
        ) : (
          <div className="space-y-4">
            {rolesQ.data.map((r) => (
              <div key={r.slug} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-text-primary">{r.name}</div>
                  <Badge>{r.slug}</Badge>
                </div>
                {r.description && <p className="mt-0.5 text-xs text-text-muted">{r.description}</p>}
                <div className="mt-2 flex flex-wrap gap-1">
                  {r.permissions.length === 0 ? (
                    <span className="text-xs text-text-muted">No permissions</span>
                  ) : (
                    r.permissions.map((p) => <Badge key={p}>{p}</Badge>)
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
