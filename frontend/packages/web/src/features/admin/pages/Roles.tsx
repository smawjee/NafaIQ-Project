import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, ExternalLink, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import { useTableSearch } from "@/features/admin/data/tableSearch";
import type { AdminRolesSearch } from "@/routes/admin.roles";
import type { AdminListItem } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  DataTable,
  EmptyBlock,
  ErrorBlock,
  formatPkt,
  PageHeader,
  Panel,
  PanelSkeleton,
  RoleBadge,
  SearchInput,
  SectionLabel,
  type Column,
} from "@/features/admin/components/ui";

export function AdminRoles() {
  const { t } = useLang();
  const { search, setSearch, setFilter } = useTableSearch<AdminRolesSearch>("/admin/roles");
  const adminQuery = search.q ?? "";
  const setAdminQuery = (v: string) => setFilter({ q: v || undefined }, { replace: true });

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
  const permsQ = useQuery({
    queryKey: ["admin-permissions"],
    queryFn: adminApi.listPermissions,
    staleTime: 5 * 60_000,
  });

  // Client-side filter: the admin list is small (tens of rows), so there's no
  // value in a server round-trip per keystroke.
  const filteredAdmins = useMemo(() => {
    const list = adminsQ.data ?? [];
    const term = adminQuery.trim().toLowerCase();
    if (!term) return list;
    return list.filter(
      (a) =>
        (a.email ?? "").toLowerCase().includes(term) ||
        a.roles.some((r) => r.toLowerCase().includes(term)),
    );
  }, [adminsQ.data, adminQuery]);

  const adminColumns = useMemo<Column<AdminListItem>[]>(
    () => [
      {
        id: "email",
        header: "Administrator",
        hideable: false,
        exportValue: (r) => r.email ?? r.user_id,
        cell: (r) => (
          <div className="flex min-w-0 items-center gap-2.5">
            <Avatar email={r.email} size="sm" />
            <Link
              to="/admin/users/$userId"
              params={{ userId: r.user_id }}
              className="truncate font-medium text-text-primary hover:text-primary hover:underline"
            >
              {r.email ?? r.user_id}
            </Link>
          </div>
        ),
      },
      {
        id: "roles",
        header: "Roles",
        exportValue: (r) => r.roles.join(" | "),
        cell: (r) => (
          <div className="flex flex-wrap gap-1">
            {r.roles.map((role) => (
              <RoleBadge key={role} role={role} />
            ))}
          </div>
        ),
      },
      {
        id: "first_granted_at",
        header: "Admin since",
        secondary: true,
        exportValue: (r) => r.first_granted_at,
        cell: (r) => (
          <span className="text-text-muted">{formatPkt(r.first_granted_at, false)}</span>
        ),
      },
      {
        id: "manage",
        header: "",
        align: "end",
        hideable: false,
        cell: (r) => (
          <Link
            to="/admin/users/$userId"
            params={{ userId: r.user_id }}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            Manage roles <ExternalLink className="h-3 w-3" aria-hidden />
          </Link>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("Roles & Access")}
        breadcrumbs={[{ label: t("Admin"), to: "/admin" }, { label: t("Roles & Access") }]}
        description="Roles and their permission mapping are fixed in the database. To grant or revoke a role, open the administrator's profile — every change is written to the audit log."
        meta={adminsQ.data && <Badge tone="neutral">{adminsQ.data.length} administrators</Badge>}
      />

      <Tabs.Root
        value={search.tab ?? "admins"}
        onValueChange={(v) => setSearch({ tab: v as AdminRolesSearch["tab"] })}
      >
        <Tabs.List
          aria-label="Access sections"
          className="flex flex-wrap gap-1 border-b border-border"
        >
          <TabTrigger value="admins">Administrators</TabTrigger>
          <TabTrigger value="roles">Roles</TabTrigger>
          <TabTrigger value="matrix">Permission matrix</TabTrigger>
        </Tabs.List>

        <Tabs.Content value="admins" className="pt-5 focus-visible:outline-none">
          <Panel flush>
            <DataTable
              label="Administrators"
              columns={adminColumns}
              rows={filteredAdmins}
              getRowId={(r) => r.user_id}
              isLoading={adminsQ.isLoading}
              isError={adminsQ.isError}
              onRetry={() => void adminsQ.refetch()}
              hasFilters={!!adminQuery}
              onClearFilters={() => setAdminQuery("")}
              emptyState={
                <EmptyBlock
                  label="No administrators found"
                  hint="Bootstrap the first admin via ADMIN_BOOTSTRAP_EMAILS, then grant roles from a user profile."
                />
              }
              toolbar={
                <SearchInput
                  value={adminQuery}
                  onChange={setAdminQuery}
                  placeholder="Filter administrators…"
                  className="max-w-xs"
                />
              }
            />
          </Panel>
        </Tabs.Content>

        <Tabs.Content value="roles" className="pt-5 focus-visible:outline-none">
          {rolesQ.isLoading ? (
            <Panel>
              <PanelSkeleton lines={6} />
            </Panel>
          ) : rolesQ.isError || !rolesQ.data ? (
            <Panel>
              <ErrorBlock onRetry={() => void rolesQ.refetch()} />
            </Panel>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {rolesQ.data.map((r) => (
                <Panel key={r.slug} className="flex flex-col">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold text-text-primary">{r.name}</h3>
                      <code className="text-[11px] text-text-muted">{r.slug}</code>
                    </div>
                    <RoleBadge role={r.slug} />
                  </div>
                  {r.description && (
                    <p className="mt-2 text-xs leading-relaxed text-text-muted">{r.description}</p>
                  )}
                  <div className="mt-3 border-t border-border pt-3">
                    <SectionLabel className="mb-1.5">
                      {r.permissions.length} permission{r.permissions.length === 1 ? "" : "s"}
                    </SectionLabel>
                    <div className="flex flex-wrap gap-1">
                      {r.permissions.length === 0 ? (
                        <span className="text-xs text-text-muted">None</span>
                      ) : (
                        r.permissions.map((p) => (
                          <code
                            key={p}
                            className="rounded border border-border bg-surface-alt px-1.5 py-0.5 text-[10px] text-text-secondary"
                          >
                            {p}
                          </code>
                        ))
                      )}
                    </div>
                  </div>
                </Panel>
              ))}
            </div>
          )}
        </Tabs.Content>

        <Tabs.Content value="matrix" className="pt-5 focus-visible:outline-none">
          <Panel
            title="Role × permission matrix"
            description="The authoritative mapping the backend uses to authorize every admin request."
            flush
          >
            {rolesQ.isLoading || permsQ.isLoading ? (
              <div className="p-4">
                <PanelSkeleton lines={8} />
              </div>
            ) : rolesQ.isError || permsQ.isError || !rolesQ.data || !permsQ.data ? (
              <ErrorBlock
                onRetry={() => {
                  void rolesQ.refetch();
                  void permsQ.refetch();
                }}
              />
            ) : (
              <PermissionMatrix
                roles={rolesQ.data}
                permissions={permsQ.data.map((p) => p.slug).sort()}
              />
            )}
          </Panel>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function PermissionMatrix({
  roles,
  permissions,
}: {
  roles: { slug: string; name: string; permissions: string[] }[];
  permissions: string[];
}) {
  const sets = useMemo(() => new Map(roles.map((r) => [r.slug, new Set(r.permissions)])), [roles]);
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border">
            <th
              scope="col"
              className="sticky start-0 z-10 bg-card px-3 py-2.5 text-start text-[11px] font-semibold uppercase tracking-wide text-text-muted"
            >
              Permission
            </th>
            {roles.map((r) => (
              <th
                key={r.slug}
                scope="col"
                className="px-2 py-2.5 text-center text-[11px] font-semibold text-text-muted"
              >
                <span className="inline-block max-w-[5.5rem] truncate" title={r.name}>
                  {r.slug.replace(/_admin$/, "").replace(/_/g, " ")}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {permissions.map((perm) => (
            <tr key={perm} className="border-b border-border/60 hover:bg-hover">
              <th
                scope="row"
                className="sticky start-0 z-10 bg-card px-3 py-2 text-start font-normal"
              >
                <code className="text-xs text-text-secondary">{perm}</code>
              </th>
              {roles.map((r) => {
                const has = sets.get(r.slug)?.has(perm) ?? false;
                return (
                  <td key={r.slug} className="px-2 py-2 text-center">
                    {has ? (
                      <Check
                        className="mx-auto h-3.5 w-3.5 text-bull"
                        aria-label={`${r.slug} has ${perm}`}
                      />
                    ) : (
                      <Minus
                        className="mx-auto h-3.5 w-3.5 text-text-muted/40"
                        aria-label={`${r.slug} does not have ${perm}`}
                      />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TabTrigger({ value, children }: { value: string; children: React.ReactNode }) {
  return (
    <Tabs.Trigger
      value={value}
      className={cn(
        "-mb-px inline-flex cursor-pointer items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium",
        "border-transparent text-text-muted transition-colors hover:text-text-primary",
        "data-[state=active]:border-primary data-[state=active]:text-primary",
      )}
    >
      {children}
    </Tabs.Trigger>
  );
}
