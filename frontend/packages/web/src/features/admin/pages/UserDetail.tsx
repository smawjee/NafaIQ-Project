import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import {
  Badge,
  EmptyBlock,
  ErrorBlock,
  formatPkt,
  LoadingBlock,
  Panel,
  StatCard,
  StatusBadge,
} from "@/features/admin/components/ui";

const PLANS = ["Free", "Pro", "Premium"];

export function AdminUserDetail() {
  const { userId } = useParams({ from: "/admin/users/$userId" });
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

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-user", userId] });

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
      toast.success("Tier updated");
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

  if (q.isLoading) return <LoadingBlock />;
  if (q.isError || !q.data) return <ErrorBlock onRetry={() => q.refetch()} />;
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
      successMessage: "Account suspended",
    });

  return (
    <div className="space-y-5">
      <Link
        to="/admin/users"
        className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> Back to users
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">{user.email ?? user.id}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-text-muted">
            <StatusBadge status={user.account_status} />
            <Badge>{user.plan}</Badge>
            {user.roles.map((r) => (
              <Badge key={r}>{r}</Badge>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {can("users.suspend") && user.account_status === "active" && (
            <button
              onClick={suspend}
              className="rounded-lg border border-bear/40 bg-bear/10 px-3 py-1.5 text-sm font-medium text-bear hover:bg-bear/15"
            >
              Suspend
            </button>
          )}
          {can("users.suspend") && user.account_status !== "active" && (
            <button
              onClick={() =>
                statusMut.mutate({ status: "active", reason: "Reactivated from admin" })
              }
              className="rounded-lg border border-bull/40 bg-bull/10 px-3 py-1.5 text-sm font-medium text-bull hover:bg-bull/15"
            >
              Reactivate
            </button>
          )}
        </div>
      </div>

      {user.status_reason && user.account_status !== "active" && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-500">
          Reason: {user.status_reason}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Profile" className="lg:col-span-1">
          <dl className="space-y-2 text-sm">
            <Row label="Display name" value={user.display_name ?? "—"} />
            <Row label="Joined" value={formatPkt(user.created_at)} />
            <Row label="Last sign-in" value={formatPkt(user.last_sign_in_at)} />
            <Row label="Email confirmed" value={formatPkt(user.email_confirmed_at)} />
            <Row label="Plan selected" value={formatPkt(user.plan_selected_at)} />
          </dl>
        </Panel>

        <Panel title="Activity" description="User-owned records" className="lg:col-span-2">
          {!user.activity.available ? (
            <EmptyBlock label="Activity metrics unavailable" />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Object.entries(user.activity.counts).map(([k, v]) => (
                <StatCard key={k} label={k.replace(/_/g, " ")} value={v.toLocaleString()} />
              ))}
            </div>
          )}
        </Panel>
      </div>

      {can("users.tier.write") && (
        <Panel title="Subscription tier" description="Manually override this user's plan">
          <div className="flex flex-wrap items-center gap-2">
            {PLANS.map((p) => (
              <button
                key={p}
                disabled={tierMut.isPending || user.plan === p}
                onClick={() => tierMut.mutate(p)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-text-primary enabled:hover:bg-hover disabled:opacity-40"
              >
                {user.plan === p ? `${p} (current)` : `Set ${p}`}
              </button>
            ))}
          </div>
        </Panel>
      )}

      {can("roles.assign") && (
        <Panel title="Admin roles" description="Grant or revoke administrative access">
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={roleToGrant}
              onChange={(e) => setRoleToGrant(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:border-primary focus:outline-none"
            >
              <option value="">Select a role…</option>
              {(rolesQ.data ?? [])
                .filter((r) => !user.roles.includes(r.slug))
                .map((r) => (
                  <option key={r.slug} value={r.slug}>
                    {r.name}
                  </option>
                ))}
            </select>
            <button
              disabled={!roleToGrant || grantMut.isPending}
              onClick={() => grantMut.mutate(roleToGrant)}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            >
              Assign
            </button>
          </div>
          {user.roles.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {user.roles.map((r) => (
                <span
                  key={r}
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-muted px-2 py-1 text-xs text-text-secondary"
                >
                  {r}
                  {can("roles.revoke") && (
                    <button
                      onClick={() =>
                        confirm({
                          title: `Revoke ${r}?`,
                          description:
                            "This removes the user's administrative access for that role.",
                          confirmText: "Revoke",
                          variant: "destructive",
                          onConfirm: async () => {
                            await revokeMut.mutateAsync(r);
                          },
                          successMessage: "Role revoked",
                        })
                      }
                      className="text-bear hover:underline"
                    >
                      revoke
                    </button>
                  )}
                </span>
              ))}
            </div>
          )}
        </Panel>
      )}

      {can("users.note") && (
        <Panel title="Admin notes" description="Internal notes — visible only to admins">
          <div className="flex items-start gap-2">
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note…"
              rows={2}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-primary focus:outline-none"
            />
            <button
              disabled={!note.trim() || noteMut.isPending}
              onClick={() => noteMut.mutate(note.trim())}
              className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            >
              Add
            </button>
          </div>
          <ul className="mt-3 space-y-2">
            {user.notes.length === 0 && <EmptyBlock label="No notes yet." />}
            {user.notes.map((n) => (
              <li
                key={n.id}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                <div className="text-text-primary">{n.note}</div>
                <div className="mt-1 text-xs text-text-muted">{formatPkt(n.created_at)}</div>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-text-primary">{value}</dd>
    </div>
  );
}
