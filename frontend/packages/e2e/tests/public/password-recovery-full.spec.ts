import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "../fixtures";

/**
 * The password reset, driven all the way through in a real browser.
 *
 * password-recovery.spec.ts covers the parts that need no account. This one
 * covers the part that does: type a REAL emailed code, set a new password, and
 * end up signed in. It exists for one reason.
 *
 * Verifying the code signs the user in BEFORE the new password is set, and
 * AuthPage has a "session exists -> go to the dashboard" effect that would
 * eject the user at step 2. `recoveryInProgress` holds that redirect until the
 * password is actually changed. Nothing else in the suite exercises that guard
 * in a browser — a mocked component test cannot, because the guard is about
 * real navigation reacting to a real Supabase session.
 *
 * The account is created and deleted here via the Supabase admin API, so no
 * real user is touched and the demo account (whose password the whole authed
 * suite depends on) is never involved.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "../../../../..");

/** Read a key from backend/.env — these are backend secrets, never VITE_ vars. */
function backendEnv(key: string): string {
  const fromProcess = process.env[key]?.trim();
  if (fromProcess) return fromProcess;

  const file = path.join(REPO_ROOT, "backend/.env");
  if (!fs.existsSync(file)) return "";
  for (const raw of fs.readFileSync(file, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1 || line.slice(0, eq).trim() !== key) continue;
    return line
      .slice(eq + 1)
      .trim()
      .replace(/^["']|["']$/g, "");
  }
  return "";
}

const SUPABASE_URL = backendEnv("SUPABASE_URL");
const SERVICE_KEY = backendEnv("SUPABASE_SECRET_KEY") || backendEnv("SUPABASE_SERVICE_ROLE_KEY");

const OLD_PASSWORD = "E2eOldPass!2026x";
const NEW_PASSWORD = "E2eNewPass!2026x";

function adminHeaders() {
  return {
    apikey: SERVICE_KEY,
    Authorization: `Bearer ${SERVICE_KEY}`,
    "Content-Type": "application/json",
  };
}

async function createUser(email: string): Promise<string> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ email, password: OLD_PASSWORD, email_confirm: true }),
  });
  if (!r.ok) throw new Error(`could not create the disposable user: ${r.status} ${await r.text()}`);
  return (await r.json()).id;
}

async function deleteUser(id: string): Promise<void> {
  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${id}`, {
    method: "DELETE",
    headers: adminHeaders(),
  });
}

/**
 * The code the user would read out of their inbox.
 *
 * generate_link mints a recovery token without sending anything, which is the
 * same call the backend makes — so this is the real code, not a stand-in.
 */
async function mintRecoveryCode(email: string): Promise<string> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/admin/generate_link`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ type: "recovery", email }),
  });
  if (!r.ok) throw new Error(`could not mint a recovery code: ${r.status} ${await r.text()}`);
  return (await r.json()).email_otp;
}

async function signInSucceeds(email: string, password: string): Promise<boolean> {
  const r = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: SERVICE_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return r.ok;
}

async function reactReady(page: import("@playwright/test").Page) {
  await page.waitForFunction(
    () => {
      const button = Array.from(document.querySelectorAll("button")).find((b) =>
        b.textContent?.trim().length,
      );
      return (
        button !== undefined && Object.keys(button).some((key) => key.startsWith("__reactProps$"))
      );
    },
    undefined,
    { timeout: 30_000 },
  );
}

test.describe("password recovery — full journey", () => {
  test.skip(
    !SUPABASE_URL || !SERVICE_KEY,
    "needs SUPABASE_URL + a service key (backend/.env) to provision a disposable account",
  );
  // Serial: each test provisions its own account, but they share the per-IP
  // rate limit on /api/auth/forgot-password.
  test.describe.configure({ mode: "serial" });

  test("a real code resets the password and lands the user in the app", async ({ page }) => {
    const email = `e2e_reset_${Date.now()}@nafaiq-test.local`;
    const userId = await createUser(email);

    try {
      await page.goto("/auth");
      await reactReady(page);
      await page.getByRole("button", { name: /^sign in$/i }).click();
      await page.getByRole("button", { name: /forgot password\?/i }).click();

      await page.locator("#reset-email").fill(email);
      await page.getByRole("button", { name: /^send code$/i }).click();
      await expect(page.locator("#reset-code")).toBeVisible();

      // Minted AFTER the request above, so this is the token that survives.
      const code = await mintRecoveryCode(email);
      await page.locator("#reset-code").fill(code);
      await page.getByRole("button", { name: /^verify code$/i }).click();

      // THE ASSERTION THIS FILE EXISTS FOR. A session now exists. Without the
      // recoveryInProgress guard the app navigates to /app right here and the
      // password is never changed.
      await expect(page.getByLabel(/^new password$/i)).toBeVisible();
      expect(new URL(page.url()).pathname).toBe("/auth");

      await page.getByLabel(/^new password$/i).fill(NEW_PASSWORD);
      await page.getByLabel(/confirm new password/i).fill(NEW_PASSWORD);
      await page.getByRole("button", { name: /^update password$/i }).click();

      // Guard released -> the normal post-auth redirect finally runs.
      await page.waitForURL((url) => url.pathname === "/app", { timeout: 30_000 });

      expect(await signInSucceeds(email, NEW_PASSWORD), "the new password must work").toBe(true);
      expect(await signInSucceeds(email, OLD_PASSWORD), "the old password must not").toBe(false);
    } finally {
      await deleteUser(userId);
    }
  });

  test("Settings changes the password of a signed-in user", async ({ page }) => {
    // The other half of the feature, and the half with no other coverage:
    // rotating a password you still know. The current password is re-checked
    // before anything changes, so an unattended signed-in browser cannot be
    // used to take the account over — that is what the wrong-password leg pins.
    // The wrong-password leg makes Supabase answer 400, which the browser logs
    // as a failed resource. That rejection IS the behaviour under test.
    test.info().annotations.push({ type: "allow-console-errors" });

    const email = `e2e_change_${Date.now()}@nafaiq-test.local`;
    const userId = await createUser(email);

    try {
      await page.goto("/auth");
      await reactReady(page);
      await page.getByRole("button", { name: /^sign in$/i }).click();
      await page.locator("#email").fill(email);
      await page.locator("#password").fill(OLD_PASSWORD);
      await page.getByRole("button", { name: /^sign in$/i }).click();
      await page.waitForURL((url) => url.pathname !== "/auth", { timeout: 30_000 });

      await page.goto("/settings");
      await reactReady(page);

      const current = page.getByLabel(/^current password$/i);
      await expect(current).toBeVisible();

      // Wrong current password: nothing may change.
      await current.fill("NotTheRightOne!1");
      await page.getByLabel(/^new password$/i).fill(NEW_PASSWORD);
      await page.getByLabel(/confirm new password/i).fill(NEW_PASSWORD);
      await page.getByRole("button", { name: /^update password$/i }).click();
      await expect(page.getByText(/current password is incorrect/i)).toBeVisible();
      expect(
        await signInSucceeds(email, OLD_PASSWORD),
        "a wrong current password must leave the account alone",
      ).toBe(true);

      // Correct current password: the rotation goes through.
      await current.fill(OLD_PASSWORD);
      await page.getByLabel(/^new password$/i).fill(NEW_PASSWORD);
      await page.getByLabel(/confirm new password/i).fill(NEW_PASSWORD);
      await page.getByRole("button", { name: /^update password$/i }).click();
      await expect(page.getByText(/password updated/i)).toBeVisible({ timeout: 20_000 });

      expect(await signInSucceeds(email, NEW_PASSWORD), "the new password must work").toBe(true);
      expect(await signInSucceeds(email, OLD_PASSWORD), "the old password must not").toBe(false);
    } finally {
      await deleteUser(userId);
    }
  });

  test("a wrong code keeps the user on the code step with the password unchanged", async ({
    page,
  }) => {
    const email = `e2e_badcode_${Date.now()}@nafaiq-test.local`;
    const userId = await createUser(email);

    try {
      await page.goto("/auth");
      await reactReady(page);
      await page.getByRole("button", { name: /^sign in$/i }).click();
      await page.getByRole("button", { name: /forgot password\?/i }).click();

      await page.locator("#reset-email").fill(email);
      await page.getByRole("button", { name: /^send code$/i }).click();
      await expect(page.locator("#reset-code")).toBeVisible();

      await page.locator("#reset-code").fill("00000000");
      await page.getByRole("button", { name: /^verify code$/i }).click();

      await expect(page.getByRole("alert")).toContainText(/invalid or has expired/i);
      await expect(page.getByLabel(/^new password$/i)).toHaveCount(0);
      expect(await signInSucceeds(email, OLD_PASSWORD), "the password must be untouched").toBe(true);
    } finally {
      await deleteUser(userId);
    }
  });
});
