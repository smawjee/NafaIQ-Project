/**
 * Quick-inspect drawer for a user, opened from the Users table.
 *
 * Deliberately read-mostly: it answers "who is this?" without losing the list
 * or its filters. The only mutation here is suspend/reactivate, because that's
 * the action admins overwhelmingly take straight from a list. Everything else
 * lives on the full profile, one click away.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ExternalLink, LogOut, ShieldCheck, ShieldOff } from "lucide-react";
import { toast } from "sonner";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import { useLang } from "@/hooks/use-lang";
import {
  Avatar,
  Badge,
  Button,
  DataRow,
  Drawer,
  ErrorBlock,
  formatNumber,
  formatPkt,
  PanelSkeleton,
  RoleBadge,
  SectionLabel,
  StatusBadge,
  humanizeKey,
} from "@/features/admin/components/ui";

export function UserQuickView({ userId, onClose }: { userId: string | null; onClose: () => void }) {
  const { t } = useLang();
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { can } = useAdmin();

  const q = useQuery({
    queryKey: ["admin-user", userId],
    queryFn: () => adminApi.getUser(userId!),
    enabled: !!userId,
  });

  // The one auth-level action offered from the list: ending sessions is a
  // common first response to a support report, and doesn't need the full
  // profile. Everything else lives behind "Open full profile".
  const signOutMut = useMutation({
    mutationFn: () => adminApi.forceSignOut(userId!),
    onSuccess: (r) => {
      toast.success(r.detail);
      void qc.invalidateQueries({ queryKey: ["admin-audit"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const statusMut = useMutation({
    mutationFn: (v: { status: string; reason: string }) =>
      adminApi.changeStatus(userId!, v.status, v.reason),
    onSuccess: () => {
      toast.success("Account status updated");
      void qc.invalidateQueries({ queryKey: ["admin-user", userId] });
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
      void qc.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const user = q.data;
  const activityCounts = Object.entries(user?.activity.counts ?? {});

  return (
    <Drawer
      open={!!userId}
      onOpenChange={(open) => !open && onClose()}
      title={user?.email ?? "User"}
      description={userId ?? undefined}
      footer={
        userId && (
          <>
            {can("users.suspend") && user && (
              <Button
                variant="ghost"
                icon={<LogOut className="h-3.5 w-3.5" />}
                loading={signOutMut.isPending}
                onClick={() => signOutMut.mutate()}
              >
                {t("Force sign-out")}
              </Button>
            )}
            {can("users.suspend") &&
              user &&
              (user.account_status === "active" ? (
                <Button
                  variant="danger"
                  icon={<ShieldOff className="h-3.5 w-3.5" />}
                  loading={statusMut.isPending}
                  onClick={() =>
                    confirm({
                      title: "Suspend this account?",
                      description: `${user.email ?? user.id} will be signed out and blocked from every authenticated action until reactivated.`,
                      confirmText: "Suspend",
                      variant: "destructive",
                      onConfirm: async () => {
                        await statusMut.mutateAsync({
                          status: "suspended",
                          reason: "Suspended from admin console",
                        });
                      },
                    })
                  }
                >
                  {t("Suspend")}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  icon={<ShieldCheck className="h-3.5 w-3.5" />}
                  loading={statusMut.isPending}
                  onClick={() =>
                    statusMut.mutate({
                      status: "active",
                      reason: "Reactivated from admin console",
                    })
                  }
                >
                  {t("Reactivate")}
                </Button>
              ))}
            <Link
              to="/admin/users/$userId"
              params={{ userId }}
              className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Open full profile <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </>
        )
      }
    >
      {q.isLoading ? (
        <PanelSkeleton lines={7} />
      ) : q.isError || !user ? (
        <ErrorBlock onRetry={() => void q.refetch()} />
      ) : (
        <div className="space-y-5">
          <div className="flex items-center gap-3">
            <Avatar email={user.email} size="lg" />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-text-primary">
                {user.display_name ?? user.email ?? user.id}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <StatusBadge status={user.account_status} />
                <Badge tone={user.plan === "Free" ? "neutral" : "accent"}>{user.plan}</Badge>
                {user.roles.map((r) => (
                  <RoleBadge key={r} role={r} />
                ))}
              </div>
            </div>
          </div>

          {user.status_reason && user.account_status !== "active" && (
            <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
              <span className="font-medium">{t("Reason:")}</span> {user.status_reason}
            </div>
          )}

          <div>
            <SectionLabel className="mb-1.5">{t("Account")}</SectionLabel>
            <dl className="rounded-lg border border-border bg-surface-alt px-3 py-1">
              <DataRow label={t("Joined")} value={formatPkt(user.created_at)} />
              <DataRow label={t("Last sign-in")} value={formatPkt(user.last_sign_in_at)} />
              <DataRow label={t("Email confirmed")} value={formatPkt(user.email_confirmed_at)} />
              <DataRow label={t("Plan selected")} value={formatPkt(user.plan_selected_at)} />
            </dl>
          </div>

          <div>
            <SectionLabel className="mb-1.5">{t("Activity")}</SectionLabel>
            {!user.activity.available || activityCounts.length === 0 ? (
              <p className="rounded-lg border border-border bg-surface-alt px-3 py-2.5 text-xs text-text-muted">
                {t("Activity metrics unavailable for this account.")}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {activityCounts.map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-border bg-surface-alt p-2.5">
                    <div className="text-[11px] text-text-muted">{humanizeKey(key)}</div>
                    <div className="tabular mt-0.5 text-base font-semibold text-text-primary">
                      {formatNumber(value)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {user.notes.length > 0 && (
            <div>
              <SectionLabel className="mb-1.5">{t("Latest note")}</SectionLabel>
              <div className="rounded-lg border border-border bg-surface-alt px-3 py-2.5">
                <p className="text-sm text-text-primary">{user.notes[0].note}</p>
                <p className="mt-1 text-[11px] text-text-muted">
                  {formatPkt(user.notes[0].created_at)}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}
