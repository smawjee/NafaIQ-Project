import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Eye, EyeOff, KeyRound, Loader2, Lock, Mail } from "lucide-react";
import { toast } from "sonner";

import { RECOVERY_CODE_MAX_LENGTH, RECOVERY_CODE_MIN_LENGTH } from "@nafaiq/shared";

import { useAuth } from "@/hooks/use-auth";
import { FloatingInput } from "@/features/auth/components/FloatingInput";
import { PasswordStrength } from "@/features/auth/components/PasswordStrength";
import { MIN_PASSWORD_LENGTH } from "@/features/auth/password-rules";
import { requestPasswordReset, setNewPassword, verifyRecoveryCode } from "@/lib/auth/recovery";
import { useLang } from "@/hooks/use-lang";

type Step = "email" | "code" | "password";

const RESEND_COOLDOWN_SECONDS = 60;
const MAX_CODE_ATTEMPTS = 5;

/**
 * Signed-out password recovery: email -> emailed numeric code -> new password.
 *
 * Rendered inside AuthPage's form column, so it inherits the page shell rather
 * than rebuilding it (same as the post-signup "confirm your email" branch).
 *
 * Two things here are deliberate and easy to "fix" into bugs:
 *  - Step 1 always advances, even when the request fails. The backend is silent
 *    about whether an address is registered; showing an error here would undo
 *    that and turn the form into an account-enumeration oracle.
 *  - `recoveryInProgress` is held from step 1 until the password is actually
 *    changed, because verifying the code signs the user in and AuthPage would
 *    otherwise redirect them to the dashboard mid-flow.
 */
export function ForgotPasswordPanel({ onBackToSignIn }: { onBackToSignIn: () => void }) {
  const { t } = useLang();
  const { setRecoveryInProgress } = useAuth();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [cooldown, setCooldown] = useState(0);

  // Release the redirect hold if the user navigates away mid-flow, so an
  // abandoned reset can't strand them on /auth with a live session.
  const releaseRef = useRef(setRecoveryInProgress);
  releaseRef.current = setRecoveryInProgress;
  useEffect(() => () => releaseRef.current(false), []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  async function sendCode(isResend = false) {
    if (busy) return;
    const address = email.trim();
    if (!address) {
      setError("Enter the email address for your account.");
      return;
    }

    setBusy(true);
    setError(null);
    setRecoveryInProgress(true);
    try {
      await requestPasswordReset(address);
    } catch {
      // Swallowed on purpose — see the note in this component's doc comment.
    } finally {
      setBusy(false);
    }

    setCooldown(RESEND_COOLDOWN_SECONDS);
    setStep("code");
    toast.success(
      isResend
        ? "If that account exists, a new code is on its way."
        : "Check your inbox for a verification code.",
    );
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (code.trim().length < RECOVERY_CODE_MIN_LENGTH) {
      setError("Enter the full code from your email.");
      return;
    }

    setBusy(true);
    setError(null);
    const { error: verifyError } = await verifyRecoveryCode(email, code);
    setBusy(false);

    if (!verifyError) {
      setStep("password");
      return;
    }

    const used = attempts + 1;
    setAttempts(used);
    if (used >= MAX_CODE_ATTEMPTS) {
      setStep("email");
      setCode("");
      setAttempts(0);
      setError("Too many incorrect codes. Request a new one.");
      return;
    }
    setError(verifyError);
  }

  async function submitPassword(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("Those passwords don't match.");
      return;
    }

    setBusy(true);
    setError(null);
    const { error: updateError } = await setNewPassword(password);
    setBusy(false);

    if (updateError) {
      setError(updateError);
      return;
    }
    // Releasing the hold lets AuthPage's redirect run: the session established
    // by the code is now a legitimately signed-in one.
    setRecoveryInProgress(false);
    toast.success("Password updated — you're signed in.");
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="space-y-5"
    >
      <div className="space-y-1.5">
        <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <KeyRound className="h-7 w-7" />
        </div>
        <h1 className="font-display text-[28px] font-bold leading-tight tracking-tight text-text-primary">
          {step === "password" ? "Choose a new password" : "Reset your password"}
        </h1>
        <p className="text-sm text-text-muted">
          {step === "email" && "We'll email you a verification code to confirm it's you."}
          {step === "code" && (
            <>
              Enter the code we sent to{" "}
              <span className="font-medium text-text-primary">{email.trim()}</span>.
            </>
          )}
          {step === "password" && "Anywhere else you're signed in will be signed out."}
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-bear/30 bg-bear/10 px-3 py-2.5 text-sm text-bear"
        >
          {error}
        </div>
      )}

      {step === "email" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void sendCode();
          }}
          className="space-y-4"
        >
          <FloatingInput
            id="reset-email"
            label="Email address"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            required
            icon={<Mail className="h-4 w-4" />}
          />
          <SubmitButton busy={busy} label="Send code" />
        </form>
      )}

      {step === "code" && (
        <form onSubmit={submitCode} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="reset-code" className="text-xs font-medium text-text-muted">
              {t("Verification code")}
            </label>
            <input
              id="reset-code"
              value={code}
              onChange={(e) =>
                setCode(e.target.value.replace(/\D/g, "").slice(0, RECOVERY_CODE_MAX_LENGTH))
              }
              inputMode="numeric"
              autoComplete="one-time-code"
              // Deliberately no maxLength: the browser applies it to the RAW
              // input, before the handler above strips separators, so pasting a
              // formatted code ("1234-5678") would lose its last digits. The
              // slice caps the cleaned value instead.
              autoFocus
              placeholder="········"
              className="h-14 w-full rounded-xl border border-border bg-surface/40 px-4 text-center font-mono text-2xl tracking-[0.3em] text-text-primary transition-all duration-200 placeholder:text-text-muted/40 focus:border-primary focus:bg-surface/70 focus:outline-none focus:ring-2 focus:ring-primary/25"
            />
          </div>
          <SubmitButton busy={busy} label="Verify code" />
          <button
            type="button"
            disabled={cooldown > 0 || busy}
            onClick={() => void sendCode(true)}
            className="w-full text-center text-sm text-text-muted transition-colors duration-200 hover:text-primary disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:text-text-muted"
          >
            {cooldown > 0 ? `Resend code in ${cooldown}s` : "Didn't get it? Resend code"}
          </button>
        </form>
      )}

      {step === "password" && (
        <form onSubmit={submitPassword} className="space-y-4">
          <div className="space-y-2.5">
            <FloatingInput
              id="reset-password"
              label="New password"
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={setPassword}
              required
              minLength={MIN_PASSWORD_LENGTH}
              autoComplete="new-password"
              icon={<Lock className="h-4 w-4" />}
              trailing={
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="text-text-muted transition-colors duration-200 hover:text-text-primary"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
            />
            {password.length > 0 && <PasswordStrength password={password} />}
          </div>
          <FloatingInput
            id="reset-confirm"
            label="Confirm new password"
            type={showPassword ? "text" : "password"}
            value={confirm}
            onChange={setConfirm}
            required
            autoComplete="new-password"
            icon={<Lock className="h-4 w-4" />}
          />
          <SubmitButton busy={busy} label="Update password" />
        </form>
      )}

      <button
        onClick={onBackToSignIn}
        className="group mx-auto flex items-center gap-1.5 text-sm text-text-muted transition-colors duration-200 hover:text-text-primary"
      >
        <ArrowLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
        {t("Back to sign in")}
      </button>
    </motion.div>
  );
}

function SubmitButton({ busy, label }: { busy: boolean; label: string }) {
  const { t } = useLang();
  return (
    <button
      type="submit"
      disabled={busy}
      className="group flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-info font-semibold text-primary-foreground shadow-[0_8px_24px_-8px_color-mix(in_oklab,var(--color-primary)_60%,transparent)] transition-all duration-200 hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:brightness-100"
    >
      {busy ? (
        <Loader2 className="h-5 w-5 animate-spin" />
      ) : (
        <>
          {t(label)}
          <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
        </>
      )}
    </button>
  );
}
