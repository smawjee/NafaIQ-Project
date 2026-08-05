import { expect, test } from "../fixtures";

/**
 * The signed-out password-recovery flow (email -> 6-digit code -> new password).
 *
 * The load-bearing assertion here is enumeration safety: an address with NO
 * account must produce exactly the same screen as one that has an account. That
 * property lives across a backend that always answers 202 and a client that
 * advances regardless — it is invisible in normal use and would regress
 * silently, which is precisely why it is pinned here.
 *
 * Boundaries, deliberately:
 *  - No reset is ever COMPLETED. Every journey stops at the code step, because
 *    finishing one needs a real inbox, and doing it against the demo account
 *    would rotate the password the whole authed suite signs in with.
 *  - The auth route is server-rendered; interacting before React attaches
 *    handlers silently no-ops. reactReady() mirrors auth-journeys.spec.ts.
 */

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

async function openForgotPassword(page: import("@playwright/test").Page) {
  await page.goto("/auth");
  await reactReady(page);
  // Default mode is sign-up; the switcher under the form is labelled "Sign In".
  await page.getByRole("button", { name: /^sign in$/i }).click();
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
  await page.getByRole("button", { name: /forgot password\?/i }).click();
  await expect(page.getByRole("heading", { name: /reset your password/i })).toBeVisible();
}

test.describe("password recovery", () => {
  test("an unregistered address is indistinguishable from a real one", async ({ page }) => {
    await openForgotPassword(page);

    await page.locator("#reset-email").fill("definitely-no-account@nafaiq.test");
    await page.getByRole("button", { name: /^send code$/i }).click();

    // Advances to the code step with no error — the whole point.
    await expect(page.locator("#reset-code")).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    await expect(page.getByText(/definitely-no-account@nafaiq\.test/)).toBeVisible();
  });

  test("submitting with no email asks for one instead of calling the server", async ({ page }) => {
    await openForgotPassword(page);

    await page.getByRole("button", { name: /^send code$/i }).click();

    await expect(page.locator("#reset-code")).toHaveCount(0);
    expect(new URL(page.url()).pathname).toBe("/auth");
  });

  test("the code field takes digits only, up to the maximum length", async ({ page }) => {
    // The field must NOT be pinned to six characters. Supabase's
    // MAILER_OTP_LENGTH is a project setting in the 6-10 range and this project
    // issues 8 — a six-character cap made the flow impossible to complete, and
    // did it silently: the user simply could not type the last two digits.
    await openForgotPassword(page);
    await page.locator("#reset-email").fill("someone@nafaiq.test");
    await page.getByRole("button", { name: /^send code$/i }).click();

    const code = page.locator("#reset-code");

    // Separators are stripped, and the cap applies to what is left — an HTML
    // maxLength would have truncated the raw text first and eaten real digits.
    await code.fill("1234-5678");
    await expect(code).toHaveValue("12345678");

    await code.fill("12345678901234");
    await expect(code).toHaveValue("1234567890");
  });

  test("a short code is rejected client-side", async ({ page }) => {
    await openForgotPassword(page);
    await page.locator("#reset-email").fill("someone@nafaiq.test");
    await page.getByRole("button", { name: /^send code$/i }).click();

    await page.locator("#reset-code").fill("123");
    await page.getByRole("button", { name: /^verify code$/i }).click();

    await expect(page.getByRole("alert")).toContainText(/full code/i);
    await expect(page.locator("#reset-code")).toBeVisible();
  });

  test("resend is on a cooldown so the form can't be used as a mail cannon", async ({ page }) => {
    await openForgotPassword(page);
    await page.locator("#reset-email").fill("someone@nafaiq.test");
    await page.getByRole("button", { name: /^send code$/i }).click();

    const resend = page.getByRole("button", { name: /resend code in \d+s/i });
    await expect(resend).toBeVisible();
    await expect(resend).toBeDisabled();
  });

  test("back to sign in returns to the sign-in form", async ({ page }) => {
    await openForgotPassword(page);

    await page.getByRole("button", { name: /back to sign in/i }).click();

    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
  });
});
