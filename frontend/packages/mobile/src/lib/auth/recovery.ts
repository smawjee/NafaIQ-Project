/**
 * Password recovery, client half. Mirror of the web module
 * (frontend/packages/web/src/lib/auth/recovery.ts) — keep the two in step.
 *
 * The backend mints the recovery token and mails a 6-digit code (see
 * backend/src/app/services/auth_recovery.py); everything after that is plain
 * Supabase auth:
 *
 *   requestPasswordReset  ->  code lands in the user's inbox
 *   verifyRecoveryCode    ->  code is exchanged for a real session
 *   setNewPassword        ->  password rotated, other sessions revoked
 *
 * A code rather than a deep link, deliberately: no custom-scheme redirect to
 * register with Supabase, nothing that breaks under Expo Go, and no cold-start
 * link handling.
 *
 * Note the middle step signs the user in BEFORE the new password is set. The
 * root layout's "signed in? go to the tabs" redirect must stand down for the
 * duration — see `recoveryInProgress` in hooks/use-auth.tsx.
 */
import type { ForgotPasswordResponse } from "@nafaiq/shared";

import { publicPost } from "@/lib/api";
import { supabase } from "@/lib/supabase";

/**
 * Ask for a code. Resolves the same way for an address with no account — the
 * endpoint is deliberately silent — so callers must always advance the UI.
 */
export async function requestPasswordReset(email: string, lang: "en" | "ur" = "en") {
  await publicPost<ForgotPasswordResponse>("/api/auth/forgot-password", {
    email: email.trim().toLowerCase(),
    lang,
  });
}

/** Exchange the emailed code for a session. Returns an error string on a bad code. */
export async function verifyRecoveryCode(
  email: string,
  code: string,
): Promise<{ error: string | null }> {
  const { error } = await supabase.auth.verifyOtp({
    email: email.trim().toLowerCase(),
    token: code.trim(),
    type: "recovery",
  });
  return { error: error ? "That code is invalid or has expired." : null };
}

/**
 * Set the password on the session established by verifyRecoveryCode, then drop
 * every OTHER session: if the account was taken over, the reset is only a real
 * recovery when it also evicts whoever was already signed in.
 */
export async function setNewPassword(password: string): Promise<{ error: string | null }> {
  const { error } = await supabase.auth.updateUser({ password });
  if (error) return { error: error.message };

  try {
    await supabase.auth.signOut({ scope: "others" });
  } catch {
    // Best effort — the password IS changed by this point, so a failure here
    // must not present to the user as a failed reset.
  }
  return { error: null };
}

/**
 * Verify the caller's current password by signing in with it. Used by the
 * change-password form so an unattended, already-signed-in device cannot be
 * used to take the account over.
 */
export async function verifyCurrentPassword(
  email: string,
  password: string,
): Promise<{ error: string | null }> {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  return { error: error ? "Current password is incorrect." : null };
}
