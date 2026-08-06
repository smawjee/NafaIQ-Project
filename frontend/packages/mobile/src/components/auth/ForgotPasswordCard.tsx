// Signed-out password recovery: email -> emailed numeric code -> new password.
//
// Rendered inside AuthExperience's glass card so it inherits the page's shell
// and keyboard handling rather than rebuilding them.
//
// Two things here are deliberate and easy to "fix" into bugs:
//  - Step 1 always advances, even when the request fails. The backend is silent
//    about whether an address is registered; surfacing an error here would undo
//    that and turn the form into an account-enumeration oracle.
//  - `recoveryInProgress` is held from step 1 until the password is actually
//    changed, because verifying the code signs the user in and the root layout
//    would otherwise redirect to the tabs mid-flow.
import { useEffect, useRef, useState } from "react";
import { Alert, Pressable, StyleSheet, TextInput, View } from "react-native";

import { RECOVERY_CODE_MAX_LENGTH, RECOVERY_CODE_MIN_LENGTH } from "@nafaiq/shared";

import { Field, PasswordField, PrimaryButton } from "@/components/auth/auth-fields";
import { Text } from "@/components/ui";
import { colors, fonts, radii } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { getCurrentLang } from "@/hooks/use-lang";
import {
  requestPasswordReset,
  setNewPassword,
  verifyRecoveryCode,
} from "@/lib/auth/recovery";

type Step = "email" | "code" | "password";

const RESEND_COOLDOWN_SECONDS = 60;
const MAX_CODE_ATTEMPTS = 5;
const MIN_PASSWORD_LENGTH = 8;

export function ForgotPasswordCard({ onBackToSignIn }: { onBackToSignIn: () => void }) {
  const { setRecoveryInProgress } = useAuth();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [cooldown, setCooldown] = useState(0);

  // Release the redirect hold if the screen goes away mid-flow, so an abandoned
  // reset can't strand the user on /auth with a live session.
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
      await requestPasswordReset(address, getCurrentLang());
    } catch {
      // Swallowed on purpose — see this file's header comment.
    } finally {
      setBusy(false);
    }

    setCooldown(RESEND_COOLDOWN_SECONDS);
    setStep("code");
    if (isResend) Alert.alert("If that account exists, a new code is on its way.");
  }

  async function submitCode() {
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

  async function submitPassword() {
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
    // Releasing the hold lets the root layout's redirect run: the session
    // established by the code is now a legitimately signed-in one.
    setRecoveryInProgress(false);
  }

  return (
    <View style={styles.root}>
      <Text variant="secondary" style={styles.blurb}>
        {step === "email" && "We'll email you a verification code to confirm it's you."}
        {step === "code" && `Enter the code we sent to ${email.trim()}.`}
        {step === "password" && "Anywhere else you're signed in will be signed out."}
      </Text>

      {error ? (
        <Text accessibilityRole="alert" style={styles.error}>
          {error}
        </Text>
      ) : null}

      {step === "email" && (
        <>
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            inputMode="email"
          />
          <PrimaryButton label="Send code" onPress={() => void sendCode()} loading={busy} />
        </>
      )}

      {step === "code" && (
        <>
          <View style={{ gap: 6 }}>
            <Text variant="secondary" style={styles.fieldLabel}>
              Verification code
            </Text>
            <TextInput
              style={styles.codeInput}
              value={code}
              onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, RECOVERY_CODE_MAX_LENGTH))}
              placeholder="········"
              placeholderTextColor={colors.textMuted}
              keyboardType="number-pad"
              textContentType="oneTimeCode"
              autoComplete="one-time-code"
              // Deliberately no maxLength: it applies to the RAW input, before
              // the handler above strips separators, so pasting a formatted
              // code ("1234-5678") would lose its last digits. The slice caps
              // the cleaned value instead.
              accessibilityLabel="Verification code"
            />
          </View>
          <PrimaryButton label="Verify code" onPress={() => void submitCode()} loading={busy} />
          <Pressable
            onPress={() => void sendCode(true)}
            disabled={cooldown > 0 || busy}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel="Resend code"
            accessibilityState={{ disabled: cooldown > 0 || busy }}
            style={styles.linkRow}
          >
            <Text variant="secondary" style={cooldown > 0 ? styles.linkDisabled : styles.link}>
              {cooldown > 0 ? `Resend code in ${cooldown}s` : "Didn't get it? Resend code"}
            </Text>
          </Pressable>
        </>
      )}

      {step === "password" && (
        <>
          <PasswordField
            label="New password"
            value={password}
            onChangeText={setPassword}
            autoComplete="new-password"
          />
          <PasswordField
            label="Confirm new password"
            value={confirm}
            onChangeText={setConfirm}
            autoComplete="new-password"
          />
          <PrimaryButton
            label="Update password"
            onPress={() => void submitPassword()}
            loading={busy}
          />
        </>
      )}

      <Pressable
        onPress={onBackToSignIn}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel="Back to sign in"
        style={styles.linkRow}
      >
        <Text style={styles.link}>Back to sign in</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: 14 },
  blurb: { fontSize: 13, lineHeight: 19 },
  fieldLabel: { fontSize: 13 },
  error: {
    color: colors.bear,
    fontSize: 13,
    lineHeight: 19,
    backgroundColor: "rgba(229,72,77,0.12)",
    borderRadius: radii.btn,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontFamily: fonts.sans,
  },
  codeInput: {
    minHeight: 56,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.14)",
    backgroundColor: "rgba(255,255,255,0.04)",
    color: colors.textPrimary,
    fontSize: 24,
    letterSpacing: 6,
    textAlign: "center",
    fontFamily: fonts.mono,
  },
  // 44pt tall so the tap target clears the accessibility minimum even though
  // the text itself is smaller.
  linkRow: { minHeight: 44, alignItems: "center", justifyContent: "center" },
  link: { color: colors.primary, fontWeight: "700" },
  linkDisabled: { opacity: 0.6 },
});
