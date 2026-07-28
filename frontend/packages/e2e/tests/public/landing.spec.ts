import { expect, test } from "../fixtures";

/**
 * J1 + J2 — the landing page and the route into sign-in.
 *
 * Assertions lean on <title> (every route sets a unique one via TanStack
 * `head()`) and accessible roles, because the whole web app ships only five
 * data-testids.
 */
test.describe("landing", () => {
  test("renders the marketing page with its conversion affordances", async ({ page }) => {
    await page.goto("/");

    await expect(page).toHaveTitle(/NafaIQ — PSX, Finance & AI in One Terminal/);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /try demo/i }).first()).toBeVisible();
  });

  test("offers a route into the auth page", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: /sign in|get started/i }).first().click();

    // "Get Started" points at /app; AuthGate then bounces an anonymous visitor
    // to /auth?redirect=%2Fapp. A glob of "**/auth" does not match that query
    // string, so match the pathname instead.
    await page.waitForURL(/\/auth/);
    await expect(page).toHaveTitle(/Sign up — NafaIQ/);
  });

  test("exposes the pricing page without a session", async ({ page }) => {
    await page.goto("/plans");

    await expect(page).toHaveTitle(/Plans & Pricing — NafaIQ/);
  });
});

test.describe("auth page", () => {
  test("shows a usable credential form", async ({ page }) => {
    await page.goto("/auth");

    await expect(page).toHaveTitle(/Sign up — NafaIQ/);
    await expect(page.getByRole("textbox", { name: /email/i }).first()).toBeVisible();
    // Password inputs have no ARIA textbox role, so target the input directly.
    await expect(page.locator('input[type="password"]').first()).toBeVisible();
  });

  test("keeps an anonymous visitor out of the dashboard", async ({ page }) => {
    await page.goto("/app");

    // AuthGate (src/routes/__root.tsx) bounces to /auth carrying the return path.
    await page.waitForURL(/\/auth/, { timeout: 15_000 });
  });
});
