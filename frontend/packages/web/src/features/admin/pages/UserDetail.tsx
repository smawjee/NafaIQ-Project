import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, ShieldCheck, ShieldOff, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { useLang } from "@/hooks/use-lang";
import { adminApi } from "@/features/admin/data/client";
import { AccountActions } from "./AccountActions";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { RoleAssignmentInfo } from "@/features/admin/data/types";
import {
  Avatar,
  Badge,
  Button,
  DataRow,
  EmptyBlock,
  ErrorBlock,
  Field,
  formatNumber,
  formatPkt,
  humanizeKey,
  KpiSkeleton,
  PageHeader,
  Panel,
  PanelSkeleton,
  PermissionDenied,
  relativeTime,
  RoleBadge,
  Select,
  StatusBadge,
  Textarea,
} from "@/features/admin/components/ui";

const PLANS = ["Free", "Pro", "Premium"];

export function AdminUserDetail() {
  const { userId } = useParams({ from: "/admin/users/$userId" });
  const { t } = useLang();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { can } = useAdmin();

  const [note, setNote] = useState("");
  const [roleToGrant, setRoleToGrant] = useState("");

  const q = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => adminApi.getUser(userId),
  });
  const rolesQ = useQuery({
    queryKey: ["admin-roles-list"],
    queryFn: adminApi.listRoles,
    enabled: can("roles.assign"),
    staleTime: 5 * 60_000,
  });
  // What this user actually experienced. Turns "it's broken for me" into
  // something checkable without asking them to reproduce it.
  const errorsQ = useQuery({
    queryKey: ["admin-user-errors", userId],
    queryFn: () => adminApi.userErrors(userId),
    enabled: can("errors.read"),
    staleTime: 30_000,
  });

  const historyQ = useQuery({
    queryKey: ["admin-user-role-history", userId],
    queryFn: () => adminApi.userRoleHistory(userId),
    enabled: can("roles.read"),
    staleTime: 60_000,
  });

  /** Refresh everything a mutation on this user can affect. */
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["admin-user", userId] });
    void qc.invalidateQueries({ queryKey: ["admin-user-role-history", userId] });
    void qc.invalidateQueries({ queryKey: ["admin-users"] });
    void qc.invalidateQueries({ queryKey: ["admin-overview"] });
    void qc.invalidateQueries({ queryKey: ["admin-admins"] });
  };

  const statusMut = useMutation({
    mutationFn: (v: { status: string; reason?: string }) =>
      adminApi.changeStatus(userId, v.status, v.reason),
    onSuccess: () => {
      toast.success("Account status updated");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const tierMut = useMutation({
    mutationFn: (plan: string) => adminApi.changeTier(userId, plan),
    onSuccess: () => {
      toast.success("Subscription tier updated");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const noteMut = useMutation({
    mutationFn: (text: string) => adminApi.addNote(userId, text),
    onSuccess: () => {
      toast.success("Note added");
      setNote("");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const grantMut = useMutation({
    mutationFn: (role: string) => adminApi.assignRole(userId, role),
    onSuccess: () => {
      toast.success("Role assigned");
      setRoleToGrant("");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const revokeMut = useMutation({
    mutationFn: (role: string) => adminApi.revokeRole(userId, role),
    onSuccess: () => {
      toast.success("Role revoked");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) {
    return (
      <div className="space-y-5">
        <PanelSkeleton lines={3} />
        <KpiSkeleton />
      </div>
    );
  }
  if (q.isError || !q.data) return <ErrorBlock onRetry={() => void q.refetch()} />;
  const user = q.data;

  const suspend = () =>
    confirm({
      title: "Suspend this account?",
      description: `${user.email ?? user.id} will be signed out and blocked from every authenticated action until reactivated.`,
      confirmText: "Suspend",
      variant: "destructive",
      onConfirm: async () => {
        await statusMut.mutateAsync({ status: "suspended", reason: "Suspended from admin" });
      },
    });

  const activityCounts = Object.entries(user.activity.counts ?? {});

  return (
    <div className="space-y-5">
      <PageHeader
        breadcrumbs={[
          { label: t("Admin"), to: "/admin" },
          { label: t("Users"), to: "/admin/users" },
          { label: user.email ?? user.id },
        ]}
        title={
          <span className="flex items-center gap-3">
            <Avatar email={user.email} size="lg" />
            <span className="min-w-0 truncate">{user.email ?? user.id}</span>
          </span>
        }
        meta={
          <span className="flex flex-wrap items-center gap-1.5">
            <StatusBadge status={user.account_status} />
            <Badge tone={user.plan === "Free" ? "neutral" : "accent"}>{user.plan}</Badge>
            {user.roles.map((r) => (
              <RoleBadge key={r} role={r} />
            ))}
          </span>
        }
        actions={
          can("users.suspend") &&
          (user.account_status === "active" ? (
            <Button
              variant="danger"
              icon={<ShieldOff className="h-3.5 w-3.5" />}
              loading={statusMut.isPending}
              onClick={suspend}
            >
              {t("Suspend")}
            </Button>
          ) : (
            <Button
              variant="outline"
              icon={<ShieldCheck className="h-3.5 w-3.5" />}
              loading={statusMut.isPending}
              onClick={() =>
                statusMut.mutate({ status: "active", reason: "Reactivated from admin" })
              }
            >
              {t("Reactivate")}
            </Button>
          ))
        }
      />

      {user.status_reason && user.account_status !== "active" && (
        <div className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          <span className="font-medium">{t("Status reason:")}</span> {user.status_reason}
          {user.status_changed_at && (
            <span className="ms-2 text-xs opacity-80">({formatPkt(user.status_changed_at)})</span>
          )}
        </div>
      )}

      <Tabs.Root defaultValue="overview">
        <Tabs.List
          aria-label={t("User sections")}
          className="flex flex-wrap gap-1 border-b border-border"
        >
          <TabTrigger value="overview">{t("Overview")}</TabTrigger>
          <TabTrigger value="access">{t("Access & roles")}</TabTrigger>
          <TabTrigger value="notes">
            {t("Notes")}{" "}
            {user.notes.length > 0 && <Badge tone="neutral">{user.notes.length}</Badge>}
          </TabTrigger>
          <TabTrigger value="history">{t("History")}</TabTrigger>
        </Tabs.List>

        {/* ---------------------------------------------------------------- */}
        <Tabs.Content value="overview" className="pt-5 focus-visible:outline-none">
          <div className="grid gap-4 lg:grid-cols-3">
            <Panel title={t("Profile")} className="lg:col-span-1">
              <dl>
                <DataRow label={t("Display name")} value={user.display_name ?? "—"} />
                <DataRow label={t("User ID")} value={<code className="text-xs">{user.id}</code>} />
                <DataRow label={t("Joined")} value={formatPkt(user.created_at)} />
                <DataRow label={t("Last sign-in")} value={formatPkt(user.last_sign_in_at)} />
                <DataRow label={t("Email confirmed")} value={formatPkt(user.email_confirmed_at)} />
                <DataRow label={t("Plan selected")} value={formatPkt(user.plan_selected_at)} />
              </dl>
            </Panel>

            <Panel
              title={t("Activity")}
              description={t("Records this user owns across the platform")}
              className="lg:col-span-2"
            >
              {!user.activity.available || activityCounts.length === 0 ? (
                <EmptyBlock
                  label={t("Activity metrics unavailable")}
                  hint={t("The per-user aggregate query failed or returned nothing.")}
                />
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {activityCounts.map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-lg border border-border bg-surface-alt p-3 transition-colors hover:border-border-hover"
                    >
                      <div className="text-[11px] text-text-muted">{humanizeKey(key)}</div>
                      <div className="tabular mt-1 text-xl font-semibold text-text-primary">
                        {formatNumber(value)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <div className="mt-4">
            {can("users.tier.write") ? (
              <Panel
                title={t("Subscription tier")}
                description={t(
                  "Manually override this user's plan. Recorded in the audit log with the before/after value.",
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  {PLANS.map((p) => {
                    const current = user.plan === p;
                    return (
                      <button
                        key={p}
                        disabled={tierMut.isPending || current}
                        onClick={() => tierMut.mutate(p)}
                        className={cn(
                          "inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border px-3 text-sm font-medium transition-all",
                          current
                            ? "border-primary/40 bg-primary/12 text-primary"
                            : "border-border text-text-secondary hover:border-border-hover hover:bg-hover hover:text-text-primary",
                          "disabled:cursor-not-allowed",
                        )}
                      >
                        {current && <Check className="h-3.5 w-3.5" aria-hidden />}
                        {p}
                        {current && <span className="text-xs opacity-70">{t("current")}</span>}
                      </button>
                    );
                  })}
                </div>
              </Panel>
            ) : (
              <Panel title={t("Subscription tier")}>
                <PermissionDenied permission="users.tier.write" />
              </Panel>
            )}
          </div>

          {can("errors.read") && (
            <div className="mt-4">
              <Panel
                title={t("Errors this user hit")}
                description={t("Captured automatically. Most recent first.")}
                flush={(errorsQ.data ?? []).length > 0}
              >
                {errorsQ.isLoading ? (
                  <PanelSkeleton lines={3} />
                ) : (errorsQ.data ?? []).length === 0 ? (
                  <EmptyBlock
                    label={t("No errors recorded for this user")}
                    hint={t("Nothing has failed for them in the retention window.")}
                  />
                ) : (
                  <ul className="divide-y divide-border">
                    {errorsQ.data!.map((e) => (
                      <li key={e.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
                        <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                          {(e as { message?: string }).message ?? "—"}
                        </span>
                        {e.route && (
                          <code className="truncate text-[11px] text-text-muted">{e.route}</code>
                        )}
                        <span className="shrink-0 text-xs text-text-muted">
                          {relativeTime(e.created_at)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>
          )}

          <div className="mt-4 space-y-4">
            <AccountActions user={user} />
          </div>
        </Tabs.Content>

        {/* ---------------------------------------------------------------- */}
        <Tabs.Content value="access" className="pt-5 focus-visible:outline-none">
          {can("roles.assign") ? (
            <Panel
              title={t("Administrative roles")}
              description={t(
                "Roles are resolved server-side from the database on every request — granting one here takes effect immediately.",
              )}
            >
              <div className="flex flex-wrap items-end gap-2">
                <Field label={t("Grant a role")} htmlFor="role-select" className="min-w-[14rem]">
                  <Select
                    id="role-select"
                    value={roleToGrant}
                    onChange={(e) => setRoleToGrant(e.target.value)}
                  >
                    <option value="">{t("Select a role…")}</option>
                    {(rolesQ.data ?? [])
                      .filter((r) => !user.roles.includes(r.slug))
                      .map((r) => (
                        <option key={r.slug} value={r.slug}>
                          {r.name}
                        </option>
                      ))}
                  </Select>
                </Field>
                <Button
                  variant="primary"
                  disabled={!roleToGrant}
                  loading={grantMut.isPending}
                  onClick={() => grantMut.mutate(roleToGrant)}
                >
                  {t("Assign")}
                </Button>
              </div>

              <div className="mt-5">
                <div className="mb-2 text-xs font-medium text-text-secondary">
                  {t("Current roles")}
                </div>
                {user.roles.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    {t("This user holds no administrative roles.")}
                  </p>
                ) : (
                  <ul className="flex flex-wrap gap-2">
                    {user.roles.map((r) => (
                      <li
                        key={r}
                        className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface-alt py-1 ps-2.5 pe-1"
                      >
                        <RoleBadge role={r} />
                        {can("roles.revoke") && (
                          <button
                            aria-label={`Revoke ${r}`}
                            onClick={() =>
                              confirm({
                                title: `Revoke ${r.replace(/_/g, " ")}?`,
                                description:
                                  "This immediately removes the administrative access that role grants.",
                                confirmText: "Revoke",
                                variant: "destructive",
                                onConfirm: async () => {
                                  await revokeMut.mutateAsync(r);
                                },
                              })
                            }
                            className="inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded text-text-muted transition-colors hover:bg-bear/15 hover:text-bear"
                          >
                            <Trash2 className="h-3 w-3" aria-hidden />
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Panel>
          ) : (
            <Panel title={t("Administrative roles")}>
              <PermissionDenied permission="roles.assign" />
            </Panel>
          )}
        </Tabs.Content>

        {/* ---------------------------------------------------------------- */}
        <Tabs.Content value="notes" className="pt-5 focus-visible:outline-none">
          {can("users.note") ? (
            <Panel
              title={t("Admin notes")}
              description={t(
                "Internal context for other administrators. Visible only inside this console.",
              )}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
                <Textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t("Add a note about this account…")}
                  rows={2}
                  aria-label={t("New admin note")}
                  className="flex-1"
                />
                <Button
                  variant="primary"
                  disabled={!note.trim()}
                  loading={noteMut.isPending}
                  onClick={() => noteMut.mutate(note.trim())}
                >
                  {t("Add note")}
                </Button>
              </div>

              <ul className="mt-4 space-y-2">
                {user.notes.length === 0 && (
                  <EmptyBlock label={t("No notes on this account yet.")} />
                )}
                {user.notes.map((n) => (
                  <li
                    key={n.id}
                    className="rounded-lg border border-border bg-surface-alt px-3 py-2.5"
                  >
                    <p className="whitespace-pre-wrap text-sm text-text-primary">{n.note}</p>
                    <p className="mt-1.5 text-[11px] text-text-muted">{formatPkt(n.created_at)}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : (
            <Panel title={t("Admin notes")}>
              <PermissionDenied permission="users.note" />
            </Panel>
          )}
        </Tabs.Content>

        {/* ---------------------------------------------------------------- */}
        <Tabs.Content value="history" className="pt-5 focus-visible:outline-none">
          <Panel
            title={t("Role assignment history")}
            description={t(
              "Every grant and revocation recorded against this account, including revoked entries.",
            )}
          >
            {!can("roles.read") ? (
              <PermissionDenied permission="roles.read" />
            ) : historyQ.isLoading ? (
              <PanelSkeleton lines={4} />
            ) : historyQ.isError ? (
              <ErrorBlock onRetry={() => void historyQ.refetch()} />
            ) : (historyQ.data ?? []).length === 0 ? (
              <EmptyBlock label={t("No role assignments have ever been made for this user.")} />
            ) : (
              <ol className="relative space-y-4 ps-4">
                {/* Timeline spine */}
                <span className="absolute inset-y-1 start-[3px] w-px bg-border" aria-hidden />
                {historyQ.data!.map((h) => (
                  <HistoryItem key={h.id} entry={h} />
                ))}
              </ol>
            )}
          </Panel>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function TabTrigger({ value, children }: { value: string; children: React.ReactNode }) {
  return (
    <Tabs.Trigger
      value={value}
      className={cn(
        "-mb-px inline-flex cursor-pointer items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium",
        "border-transparent text-text-muted transition-colors",
        "hover:text-text-primary",
        "data-[state=active]:border-primary data-[state=active]:text-primary",
      )}
    >
      {children}
    </Tabs.Trigger>
  );
}

function HistoryItem({ entry }: { entry: RoleAssignmentInfo }) {
  const revoked = !!entry.revoked_at;
  return (
    <li className="relative">
      <span
        className={cn(
          "absolute -start-4 top-1.5 h-1.5 w-1.5 rounded-full ring-4 ring-card",
          revoked ? "bg-bear" : "bg-bull",
        )}
        aria-hidden
      />
      <div className="flex flex-wrap items-center gap-2">
        <RoleBadge role={entry.role_slug} />
        <span className={cn("text-xs font-medium", revoked ? "text-bear" : "text-bull")}>
          {revoked ? "Revoked" : "Granted"}
        </span>
        <span className="text-xs text-text-muted">
          {formatPkt(revoked ? entry.revoked_at : entry.granted_at)}
        </span>
      </div>
      {entry.reason && <p className="mt-1 text-xs text-text-muted">Reason: {entry.reason}</p>}
    </li>
  );
}
