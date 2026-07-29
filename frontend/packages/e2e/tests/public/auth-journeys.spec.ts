import { expect, test } from "../fixtures";
import { VITE_ENV } from "../../playwright.config";

/**
 * Interactive auth-page journeys (workbook TC-AUTH-02/03/04/05/06/08):
 * sign-up validation, the password strength meter, and real sign-ins through
 * the visible form using the demo credentials.
 *
 * Boundaries, deliberately:
 *  - No account is ever CREATED — the sign-up submissions here are exactly
 *    the ones client-side validation rejects before any network call
 *    (AuthPage.tsx validates name and password length before calling
 *    supabase), so the shared Supabase project is never polluted.
 *  - Sign-ins use the demo account. A password-grant sign-in mints a NEW
 *    session and does not disturb the shared storageState session the authed
 *    projects run on. (Sign-OUT would revoke it — which is why there is no
 *    logout journey here; it needs a dedicated throwaway account.)
 *  - The auth route is server-rendered; interacting before React attaches
 *    handlers silently no-ops. reactReady() mirrors auth.setup.ts.
 */

const email = VITE_ENV.VITE_DEMO_EMAIL ?? "";
const password = VITE_ENV.VITE_DEMO_PASSWORD ?? "";

async function reactReady(page: import("@playwright/test").Page) {
  await page.waitForFunction(
    () => {
      const button = Array.from(document.querySelectorAll("button")).find((b) =>
        b.textContent?.trim().length,
      );
      return (
        button !== undefined &&
        Object.keys(button).some((key) => key.startsWith("__reactProps$"))
      );
    },
    undefined,
    { timeout: 30_000 },
  );
}

async function switchToSignIn(page: import("@playwright/test").Page) {
  await reactReady(page);
  // Default mode is sign-up; the switcher under the form is labelled "Sign In".
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
}

test.describe("sign-up validation", () => {
  test("the strength meter tracks the password as it is typed", async ({ page }) => {
    await page.goto("/auth");
    await reactReady(page);

    const pw = page.locator("#password");
    await pw.fill("a");
    await expect(page.getByText("Too weak", { exact: true })).toBeVisible();
    await pw.fill("aA");
    await expect(page.getByText("Weak", { exact: true })).toBeVisible();
    await pw.fill("aA1");
    await expect(page.getByText("Fair", { exact: true })).toBeVisible();
    await pw.fill("aA1!");
    await expect(page.getByText("Good", { exact: true })).toBeVisible();
    await pw.fill("aA1!2345");
    await expect(page.getByText("Strong", { exact: true })).toBeVisible();
  });

  test("an empty name blocks account creation with a clear message", async ({ page }) => {
    await page.goto("/auth");
    await reactReady(page);

    // Names left empty; everything else valid. The name guard runs BEFORE any
    // network call, so nothing is created.
    await page.locator("#email").fill("e2e-never-created@nafaiq.test");
    await page.locator("#password").fill("Passw0rd!23");
    await page.getByRole("button", { name: /^create account$/i }).click();

    await expect(page.getByText("Please enter your name")).toBeVisible();
    expect(new URL(page.url()).pathname).toBe("/auth");
  });

  test("a short password cannot be submitted", async ({ page }) => {
    await page.goto("/auth");
    await reactReady(page);

    await page.locator("#firstName").fill("Ali");
    await page.locator("#lastName").fill("Khan");
    await page.locator("#email").fill("e2e-never-created@nafaiq.test");
    const pw = page.locator("#password");
    await pw.fill("Ab1!");
    await page.getByRole("button", { name: /^create account$/i }).click();

    // The input's minLength=8 stops submission at the browser layer — the
    // form must still be on /auth with the field flagged too-short.
    expect(await pw.evaluate((el: HTMLInputElement) => el.validity.tooShort)).toBe(true);
    expect(new URL(page.url()).pathname).toBe("/auth");
  });
});

test.describe("sign-in", () => {
  test.skip(!email || !password, "demo credentials not configured");

  test("correct credentials land on the dashboard", async ({ page }) => {
    await page.goto("/auth");
    await switchToSignIn(page);

    await page.locator("#email").fill(email);
    await page.locator("#password").fill(password);
    await page.getByRole("button", { name: /^sign in$/i }).click();

    await page.waitForURL((url) => url.pathname === "/app", { timeout: 30_000 });
    await expect(page).toHaveTitle(/Dashboard — NafaIQ/);
  });

  test("a wrong password fails with an error, not a silent no-op", async ({ page }) => {
    // Supabase answers 400 and the browser logs the failed resource — that
    // rejection is the behaviour under test.
    test.info().annotations.push({ type: "allow-console-errors" });

    await page.goto("/auth");
    await switchToSignIn(page);

    await page.locator("#email").fill(email);
    await page.locator("#password").fill("WrongPass1!!");
    await page.getByRole("button", { name: /^sign in$/i }).click();

    await expect(page.getByText(/invalid login credentials/i)).toBeVisible();
    expect(new URL(page.url()).pathname).toBe("/auth");
  });

  test("login returns the user to the page they originally asked for", async ({ page }) => {
    await page.goto("/auth?redirect=/portfolio");
    await switchToSignIn(page);

    await page.locator("#email").fill(email);
    await page.locator("#password").fill(password);
    await page.getByRole("button", { name: /^sign in$/i }).click();

    await page.waitForURL((url) => url.pathname === "/portfolio", { timeout: 30_000 });
    await expect(page).toHaveTitle(/Portfolio — NafaIQ/);
  });
});
