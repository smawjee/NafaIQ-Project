import { useNavigate, Link, useSearch } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Loader2,
  Eye,
  EyeOff,
  Check,
  X,
  ArrowLeft,
  ArrowRight,
  MailCheck,
  Mail,
  Lock,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { usePlatformFlags } from "@/hooks/use-platform-flags";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { formContainer, formItem } from "@/features/auth/auth.data";
import { LogoIcon } from "@/features/auth/components/LogoIcon";
import { GoogleButton } from "@/features/auth/components/GoogleButton";
import { FloatingInput } from "@/features/auth/components/FloatingInput";
import { AuthVisualPanel } from "@/features/auth/components/AuthVisualPanel";

export function AuthPage() {
  const { user, loading, signInWithPassword, signUpWithPassword, signInWithGoogle } = useAuth();
  const { signInAsDemo } = useDemo();
  const { theme } = useLandingTheme();
  const isLight = theme === "light";
  const navigate = useNavigate();
  const { redirect } = useSearch({ from: "/auth" });

  const [mode, setMode] = useState<"signin" | "signup">("signup");
  const { registrationEnabled, maintenanceMode } = usePlatformFlags();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);

  const destination =
    redirect && redirect.startsWith("/") && redirect !== "/" && !redirect.startsWith("/auth")
      ? redirect
      : "/app";

  // Fallback: if a session already exists (or arrives via OAuth/email link), go in.
  useEffect(() => {
    if (!loading && user) navigate({ to: destination });
  }, [user, loading, navigate, destination]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      if (mode === "signup") {
        const name = `${firstName} ${lastName}`.trim();
        if (name.length < 2) {
          toast.error("Please enter your name");
          return;
        }
        if (password.length < 8) {
          toast.error("Password must be at least 8 characters");
          return;
        }
        const { error, needsConfirmation } = await signUpWithPassword(email.trim(), password, name);
        if (error) return toast.error(error);
        if (needsConfirmation) {
          setConfirmSent(true);
          toast.success("Confirmation email sent — check your inbox.");
          return;
        }
        toast.success("Account created — welcome to NafaIQ!");
        navigate({ to: destination });
      } else {
        const { error } = await signInWithPassword(email.trim(), password);
        if (error) return toast.error(error);
        toast.success("Welcome back!");
        navigate({ to: destination });
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleGoogle() {
    setBusy(true);
    const { error } = await signInWithGoogle();
    if (error) {
      toast.error(error);
      setBusy(false);
    }
  }

  // Registration closed by an administrator: fall back to sign-in rather than
  // leaving the user on a form that cannot succeed.
  const isSignup = mode === "signup" && registrationEnabled;

  const pwChecks = [
    { label: "At least 8 characters", ok: password.length >= 8 },
    { label: "One uppercase letter", ok: /[A-Z]/.test(password) },
    { label: "One number", ok: /[0-9]/.test(password) },
    { label: "One special character", ok: /[^A-Za-z0-9]/.test(password) },
  ];
  const pwScore = pwChecks.filter((c) => c.ok).length;
  const strengthMeta = [
    { label: "Too weak", color: "var(--color-bear)" },
    { label: "Weak", color: "var(--color-bear)" },
    { label: "Fair", color: "var(--color-warning)" },
    { label: "Good", color: "var(--color-gold)" },
    { label: "Strong", color: "var(--color-primary)" },
  ][pwScore];

  // Derive which guided step is active so the visual panel mirrors form progress.
  const currentStep = confirmSent
    ? 3
    : !isSignup
      ? 2
      : firstName.trim() && lastName.trim()
        ? email.trim() && password.length >= 8
          ? 3
          : 2
        : 1;

  return (
    <main
      className={`relative flex min-h-screen w-full flex-col overflow-hidden p-2 transition-all duration-500 selection:bg-primary/30 md:p-4 bg-background ${isLight ? "landing-light" : ""}`}
    >
      {/* ---------- Top nav (overlay, spans both columns) ---------- */}
      <nav className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-center justify-between px-5 py-5 md:px-7 md:py-7">
        <div
          className={`pointer-events-auto flex items-center gap-2.5 ${isLight ? "rounded-xl bg-black/15 px-3 py-2 backdrop-blur-sm" : ""}`}
        >
          <LogoIcon className="h-9 w-9 rounded-[8px] ring-1 ring-bull/30" />
          <span
            className={`font-display text-2xl font-bold tracking-tight ${isLight ? "text-white" : "text-text-primary"}`}
          >
            Nafa<span className="text-primary">IQ</span>
          </span>
        </div>
        <Link
          to="/"
          className="group pointer-events-auto inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-surface/40 px-3.5 py-2 text-xs font-medium text-text-muted backdrop-blur-md transition-all duration-200 hover:border-white/20 hover:text-text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" />
          Back to home
        </Link>
      </nav>

      {/* ---------- Columns (flush, no gap) ---------- */}
      <div className="relative z-10 flex flex-1 flex-col-reverse overflow-hidden md:flex-row-reverse">
        {/* Form column — solid dark panel, form sits directly inside */}
        <div
          className={`relative flex flex-1 items-center justify-center overflow-hidden rounded-3xl px-4 py-8 sm:px-8 lg:px-12 md:rounded-l-none md:rounded-r-3xl ${isLight ? "bg-white" : "bg-zinc-950"}`}
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="relative z-10 mx-auto flex h-full w-full max-w-[480px] flex-col justify-center"
          >
            {confirmSent ? (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="space-y-6 text-center"
              >
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <MailCheck className="h-8 w-8" />
                </div>
                <div className="space-y-2">
                  <h2 className="font-display text-2xl font-bold tracking-tight text-text-primary">
                    Confirm your email
                  </h2>
                  <p className="text-sm text-text-muted">
                    We sent a confirmation link to{" "}
                    <span className="font-medium text-text-primary">{email}</span>. Click the link
                    to activate your NafaIQ account, then sign in.
                  </p>
                </div>
                <button
                  onClick={() => {
                    setConfirmSent(false);
                    setMode("signin");
                  }}
                  className="flex h-[52px] w-full items-center justify-center rounded-xl bg-primary py-3.5 font-semibold text-primary-foreground transition-all duration-200 hover:bg-primary/90 active:scale-[0.98]"
                >
                  Go to Sign In
                </button>
              </motion.div>
            ) : (
              <div className="space-y-5">
                <div className="space-y-1.5">
                  <h1 className="font-display text-[28px] font-bold leading-tight tracking-tight text-text-primary">
                    {isSignup ? "Create your account" : "Welcome back"}
                  </h1>
                  <p className="text-sm text-text-muted">
                    {isSignup
                      ? "Start your journey with intelligent PSX insights."
                      : "Sign in to your NafaIQ terminal."}
                  </p>
                </div>

                {maintenanceMode && (
                  <div className="rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm text-warning">
                    NafaIQ is undergoing scheduled maintenance. You may not be able to sign in until
                    it completes.
                  </div>
                )}

                {!registrationEnabled && (
                  <div className="rounded-xl border border-border bg-surface-alt px-3 py-2.5 text-sm text-text-secondary">
                    New sign-ups are temporarily closed. Existing accounts can still sign in.
                  </div>
                )}

                <GoogleButton onClick={handleGoogle} disabled={busy || maintenanceMode} />

                <div className="relative flex items-center">
                  <div className="flex-1 border-t border-border" />
                  <span className="px-3 text-xs font-medium text-text-muted">
                    Or continue with email
                  </span>
                  <div className="flex-1 border-t border-border" />
                </div>

                <motion.form
                  onSubmit={handleSubmit}
                  className="space-y-4"
                  variants={formContainer}
                  initial="hidden"
                  animate="show"
                >
                  {isSignup && (
                    <motion.div variants={formItem} className="grid grid-cols-2 gap-3">
                      <FloatingInput
                        id="firstName"
                        label="First name"
                        type="text"
                        value={firstName}
                        onChange={setFirstName}
                        autoComplete="given-name"
                        icon={<User className="h-4 w-4" />}
                      />
                      <FloatingInput
                        id="lastName"
                        label="Last name"
                        type="text"
                        value={lastName}
                        onChange={setLastName}
                        autoComplete="family-name"
                        icon={<User className="h-4 w-4" />}
                      />
                    </motion.div>
                  )}

                  <motion.div variants={formItem}>
                    <FloatingInput
                      id="email"
                      label="Email address"
                      type="email"
                      value={email}
                      onChange={setEmail}
                      autoComplete="email"
                      required
                      icon={<Mail className="h-4 w-4" />}
                    />
                  </motion.div>

                  <motion.div variants={formItem} className="space-y-2.5">
                    <FloatingInput
                      id="password"
                      label="Password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={setPassword}
                      required
                      minLength={8}
                      autoComplete={isSignup ? "new-password" : "current-password"}
                      icon={<Lock className="h-4 w-4" />}
                      trailing={
                        <button
                          type="button"
                          onClick={() => setShowPassword((s) => !s)}
                          className="text-text-muted transition-colors duration-200 hover:text-text-primary"
                          aria-label={showPassword ? "Hide password" : "Show password"}
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      }
                    />

                    {isSignup && password.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        className="space-y-2.5 pt-0.5"
                      >
                        <div className="flex items-center gap-2">
                          <div className="flex h-1.5 flex-1 gap-1">
                            {[0, 1, 2, 3].map((i) => (
                              <div
                                key={i}
                                className="flex-1 rounded-full transition-colors duration-200"
                                style={{
                                  backgroundColor:
                                    i < pwScore ? strengthMeta.color : "var(--color-border)",
                                }}
                              />
                            ))}
                          </div>
                          <span
                            className="text-xs font-medium"
                            style={{ color: strengthMeta.color }}
                          >
                            {strengthMeta.label}
                          </span>
                        </div>
                        <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5">
                          {pwChecks.map((c) => (
                            <li
                              key={c.label}
                              className="flex items-center gap-1.5 text-xs transition-colors duration-200"
                              style={{
                                color: c.ok ? "var(--color-primary)" : "var(--color-text-muted)",
                              }}
                            >
                              <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                                {c.ok ? (
                                  <Check className="h-3.5 w-3.5" />
                                ) : (
                                  <X className="h-3.5 w-3.5 opacity-50" />
                                )}
                              </span>
                              {c.label}
                            </li>
                          ))}
                        </ul>
                      </motion.div>
                    )}
                  </motion.div>

                  <motion.button
                    variants={formItem}
                    type="submit"
                    disabled={busy || maintenanceMode}
                    className="group mt-2 flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-primary to-info font-semibold text-primary-foreground shadow-[0_8px_24px_-8px_color-mix(in_oklab,var(--color-primary)_60%,transparent)] transition-all duration-200 hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:brightness-100"
                  >
                    {busy ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <>
                        {isSignup ? "Create Account" : "Sign In"}
                        <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                      </>
                    )}
                  </motion.button>
                </motion.form>

                <div className="space-y-3 text-center">
                  {(isSignup || registrationEnabled) && (
                    <p className="text-sm text-text-muted">
                      {isSignup ? "Already have an account? " : "New to NafaIQ? "}
                      <button
                        onClick={() => setMode(isSignup ? "signin" : "signup")}
                        className="font-medium text-primary transition-colors duration-200 hover:underline"
                      >
                        {isSignup ? "Sign In" : "Create one"}
                      </button>
                    </p>
                  )}
                  {isSignup && (
                    <p className="text-xs leading-relaxed text-text-muted/80">
                      By creating an account you agree to the{" "}
                      <a
                        href="#"
                        className="text-text-secondary hover:text-primary hover:underline"
                      >
                        Terms
                      </a>{" "}
                      &amp;{" "}
                      <a
                        href="#"
                        className="text-text-secondary hover:text-primary hover:underline"
                      >
                        Privacy Policy
                      </a>
                      .
                    </p>
                  )}
                  <div className="relative flex items-center pt-2">
                    <div className="flex-1 border-t border-border" />
                    <span className="px-3 text-xs font-medium text-text-muted">or</span>
                    <div className="flex-1 border-t border-border" />
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        await signInAsDemo();
                      } catch {
                        toast.error("Demo account not configured on this instance");
                      }
                    }}
                    className="group mt-1 flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-border bg-surface text-sm font-medium text-text-secondary transition-all duration-200 hover:border-white/[0.12] hover:text-text-primary active:scale-[0.98]"
                  >
                    Try Demo
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </div>

        <AuthVisualPanel currentStep={currentStep} isLight={isLight} />
      </div>
    </main>
  );
}
