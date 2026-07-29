/**
 * Account lifecycle actions for a single user.
 *
 * Split from UserDetail because these are a different kind of action: suspend
 * and tier changes are routine and reversible, whereas these reach into the auth
 * system — ending sessions, mailing the account holder, and destroying identity.
 * Grouping them under one clearly-labelled heading is what stops an admin
 * clicking "Anonymise" while aiming for "Suspend".
 */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, MailCheck, ShieldX } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useConfirm } from "@/components/shared/ConfirmDialog";
import { adminApi } from "@/features/admin/data/client";
import { useAdmin } from "@/features/admin/data/useAdmin";
import type { UserDetail } from "@/features/admin/data/types";
import { Button, Drawer, Input, Panel } from "@/features/admin/components/ui";

export function AccountActions({ user }: { user: UserDetail }) {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const { t } = useLang();
  const { can } = useAdmin();
  const [anonOpen, setAnonOpen] = useState(false);

  const canManage = can("users.suspend");
  const canAnonymise = can("users.anonymise");

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["admin-user", user.id] });
    void qc.invalidateQueries({ queryKey: ["admin-users"] });
    void qc.invalidateQueries({ queryKey: ["admin-audit"] });
  };

  const signOutMut = useMutation({
    mutationFn: () => adminApi.forceSignOut(user.id),
    onSuccess: (r) => {
      toast.success(r.detail);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const resetMut = useMutation({
    mutationFn: () => adminApi.sendPasswordReset(user.id),
    onSuccess: (r) => {
      toast.success(r.detail);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const verifyMut = useMutation({
    mutationFn: () => adminApi.resendVerification(user.id),
    onSuccess: (r) => {
      toast.success(r.detail);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Bail out AFTER the hooks above — an early return before them would change
  // hook order between renders when permissions resolve.
  if (!canManage && !canAnonymise) return null;

  return (
    <>
      {canManage && (
        <Panel
          title={t("Account actions")}
          description={t(
            "These reach into the authentication system. Every one is recorded in the audit log.",
          )}
        >
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              icon={<LogOut className="h-3.5 w-3.5" />}
              loading={signOutMut.isPending}
              onClick={() =>
                confirm({
                  title: t("Sign this user out everywhere?"),
                  description: t(
                    "Revokes every active session immediately. They can sign in again straight away — use Suspend if you want to block access.",
                  ),
                  confirmText: t("Sign out"),
                  onConfirm: async () => {
                    await signOutMut.mutateAsync();
                  },
                })
              }
            >
              {t("Force sign-out")}
            </Button>

            <Button
              variant="secondary"
              icon={<KeyRound className="h-3.5 w-3.5" />}
              loading={resetMut.isPending}
              onClick={() =>
                confirm({
                  title: t("Send a password reset email?"),
                  description: t(
                    "The reset link goes to the account holder's own inbox. It is never shown to administrators.",
                  ),
                  confirmText: t("Send email"),
                  onConfirm: async () => {
                    await resetMut.mutateAsync();
                  },
                })
              }
            >
              {t("Send password reset")}
            </Button>

            {/* Only meaningful while the address is unconfirmed — the server
                409s otherwise, so don't offer a button that can only fail. */}
            {!user.email_confirmed_at && (
              <Button
                variant="secondary"
                icon={<MailCheck className="h-3.5 w-3.5" />}
                loading={verifyMut.isPending}
                onClick={() => verifyMut.mutate()}
              >
                {t("Resend verification")}
              </Button>
            )}
          </div>
        </Panel>
      )}

      {canAnonymise && (
        <Panel
          title={t("Danger zone")}
          className="border-bear/30"
          description={t(
            "Irreversible. Use for erasure requests — personal data is destroyed, activity records are kept.",
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-lg text-sm text-text-secondary">
              {t(
                "Anonymising replaces the email address with an unroutable placeholder, clears the display name and ends all sessions. Portfolios, transactions and finance records are kept so platform totals stay accurate.",
              )}
            </p>
            <Button
              variant="danger"
              icon={<ShieldX className="h-3.5 w-3.5" />}
              onClick={() => setAnonOpen(true)}
            >
              {t("Anonymise account")}
            </Button>
          </div>
        </Panel>
      )}

      <AnonymiseDialog user={user} open={anonOpen} onOpenChange={setAnonOpen} onDone={invalidate} />
    </>
  );
}

/* -------------------------------------------------------------------------- */

/**
 * Typed confirmation rather than the shared confirm dialog.
 *
 * A one-click "Are you sure?" is calibrated for reversible actions. This one
 * destroys an identity permanently, so it asks the admin to retype the address —
 * which also forces them to look at *which* account they're about to erase.
 */
function AnonymiseDialog({
  user,
  open,
  onOpenChange,
  onDone,
}: {
  user: UserDetail;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onDone: () => void;
}) {
  const { t } = useLang();
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("");

  const expected = user.email ?? user.id;
  const matches = typed.trim().toLowerCase() === expected.toLowerCase();

  const mut = useMutation({
    mutationFn: () => adminApi.anonymiseUser(user.id, reason.trim() || undefined),
    onSuccess: (r) => {
      toast.success(r.detail);
      onOpenChange(false);
      setTyped("");
      setReason("");
      onDone();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Drawer
      open={open}
      onOpenChange={(v) => {
        onOpenChange(v);
        if (!v) setTyped("");
      }}
      title={t("Anonymise this account")}
      description={expected}
      width="sm"
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("Cancel")}
          </Button>
          <Button
            variant="danger"
            disabled={!matches}
            loading={mut.isPending}
            onClick={() => mut.mutate()}
          >
            {t("Anonymise permanently")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-lg border border-bear/30 bg-bear/10 px-3 py-2.5 text-sm text-bear">
          {t("This cannot be undone. The original email address will not be recoverable.")}
        </div>

        <ul className="space-y-1.5 text-sm text-text-secondary">
          <li>• {t("Email replaced with an unroutable placeholder")}</li>
          <li>• {t("Display name cleared")}</li>
          <li>• {t("All sessions revoked and the account suspended")}</li>
          <li>• {t("Portfolios, transactions and finance records are kept")}</li>
        </ul>

        <div className="space-y-1.5">
          <label htmlFor="anon-confirm" className="block text-xs font-medium text-text-secondary">
            {t("Type the account's email to confirm")}
          </label>
          <Input
            id="anon-confirm"
            value={typed}
            autoComplete="off"
            onChange={(e) => setTyped(e.target.value)}
            placeholder={expected}
            className={cn(typed && !matches && "border-bear")}
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="anon-reason" className="block text-xs font-medium text-text-secondary">
            {t("Reason (optional, recorded in the audit log)")}
          </label>
          <Input
            id="anon-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("e.g. user erasure request")}
          />
        </div>
      </div>
    </Drawer>
  );
}
