import { useState } from "react";
import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Card } from "@/components/shared/Card";
import { PasswordStrength } from "@/features/auth/components/PasswordStrength";
import { MIN_PASSWORD_LENGTH } from "@/features/auth/password-rules";
import { setNewPassword, verifyCurrentPassword } from "@/lib/auth/recovery";

/**
 * Rotate the password of the signed-in account.
 *
 * The current password is re-checked before anything changes. Without that, an
 * unattended signed-in browser is enough to take the account over permanently —
 * a session is a weaker thing to trust than the password itself.
 */
export function ChangePasswordCard({ email, t }: { email: string; t: (s: string) => string }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    if (next.length < MIN_PASSWORD_LENGTH) {
      toast.error(t("Password must be at least 8 characters."));
      return;
    }
    if (next !== confirm) {
      toast.error(t("Those passwords don't match."));
      return;
    }
    if (next === current) {
      toast.error(t("Your new password must be different from your current one."));
      return;
    }

    setBusy(true);
    try {
      const check = await verifyCurrentPassword(email, current);
      if (check.error) {
        toast.error(t("Current password is incorrect."));
        return;
      }

      const { error } = await setNewPassword(next);
      if (error) {
        toast.error(error);
        return;
      }

      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success(t("Password updated. Other devices have been signed out."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center gap-2">
        <KeyRound className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold text-text-primary">{t("Password")}</h2>
      </div>
      <p className="mb-4 text-[13px] text-text-muted">
        {t("Changing your password signs you out everywhere else.")}
      </p>

      <form onSubmit={submit} className="max-w-md space-y-3">
        <Field
          id="current-password"
          label={t("Current password")}
          value={current}
          onChange={setCurrent}
          type={show ? "text" : "password"}
          autoComplete="current-password"
        />
        <div className="space-y-2.5">
          <Field
            id="new-password"
            label={t("New password")}
            value={next}
            onChange={setNext}
            type={show ? "text" : "password"}
            autoComplete="new-password"
            trailing={
              <button
                type="button"
                onClick={() => setShow((s) => !s)}
                className="text-text-muted transition-colors duration-200 hover:text-text-primary"
                aria-label={show ? t("Hide password") : t("Show password")}
              >
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
          />
          {next.length > 0 && <PasswordStrength password={next} />}
        </div>
        <Field
          id="confirm-password"
          label={t("Confirm new password")}
          value={confirm}
          onChange={setConfirm}
          type={show ? "text" : "password"}
          autoComplete="new-password"
        />

        <button
          type="submit"
          disabled={busy || !current || !next || !confirm}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:bg-primary/90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {t("Update password")}
        </button>
      </form>
    </Card>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type,
  autoComplete,
  trailing,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type: string;
  autoComplete: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-xs font-medium text-text-muted">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          className="h-10 w-full rounded-lg border border-border bg-surface/40 px-3 text-sm text-text-primary transition-all duration-200 focus:border-primary focus:bg-surface/70 focus:outline-none focus:ring-2 focus:ring-primary/25"
          style={trailing ? { paddingInlineEnd: "2.5rem" } : undefined}
        />
        {trailing && <span className="absolute inset-y-0 end-3 flex items-center">{trailing}</span>}
      </div>
    </div>
  );
}
