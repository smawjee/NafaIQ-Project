/**
 * One definition of "is this password good enough", shared by sign-up, the
 * forgot-password flow, and the change-password card in Settings. Previously
 * inlined in AuthPage; three copies would have drifted.
 *
 * The labels are asserted verbatim by the e2e suite
 * (e2e/tests/public/auth-journeys.spec.ts) — rewording them breaks those tests.
 */

export type PasswordCheck = { label: string; ok: boolean };

/** Minimum length the sign-up and reset forms enforce before submitting. */
export const MIN_PASSWORD_LENGTH = 8;

export function passwordChecks(password: string): PasswordCheck[] {
  return [
    { label: "At least 8 characters", ok: password.length >= MIN_PASSWORD_LENGTH },
    { label: "One uppercase letter", ok: /[A-Z]/.test(password) },
    { label: "One number", ok: /[0-9]/.test(password) },
    { label: "One special character", ok: /[^A-Za-z0-9]/.test(password) },
  ];
}

const STRENGTH = [
  { label: "Too weak", color: "var(--color-bear)" },
  { label: "Weak", color: "var(--color-bear)" },
  { label: "Fair", color: "var(--color-warning)" },
  { label: "Good", color: "var(--color-gold)" },
  { label: "Strong", color: "var(--color-primary)" },
];

export function passwordStrength(password: string) {
  const checks = passwordChecks(password);
  const score = checks.filter((c) => c.ok).length;
  return { checks, score, ...STRENGTH[score] };
}
