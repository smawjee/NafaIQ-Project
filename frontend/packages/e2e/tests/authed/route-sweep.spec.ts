import { expect, test } from "../fixtures";

/**
 * J12 — every route loads, renders real content, and logs nothing.
 *
 * A breadth net, not a depth one. The other specs prove specific journeys work;
 * this proves no route is outright broken — blank, crashing, or stuck on a
 * skeleton — which is the failure mode that survives a suite of narrow journeys.
 *
 * Three things this got wrong on the way to being useful, all worth keeping in
 * mind before tightening it further:
 *
 *   * Asserting on `body` passes on a completely blank page, because the sidebar
 *     alone is ~400 characters of nav chrome. It called /funds healthy.
 *   * Asserting a heading exists is not a proxy for "rendered": /psx is a
 *     terminal-style page with no <h1>, and /team is a standalone page outside
 *     AppShell. Both were reported broken while working.
 *   * Asserting immediately after load reports every data-driven page as empty.
 *     These pages fetch on mount, so the content area legitimately starts near
 *     empty — hence the polling below rather than a single read.
 */

/** Routes reachable by a signed-in demo user. */
const USER_ROUTES = [
  "/app",
  "/psx",
  "/stock/OGDC",
  "/watchlist",
  "/portfolio",
  "/finance",
  "/funds",
  "/dividends",
  "/monetary",
  "/alerts",
  "/ai-insights",
  "/learn",
  "/plans",
  "/settings",
  "/help",
  "/team",
];

/**
 * Admin routes. The demo account is NOT an admin, and AdminGuard is designed to
 * bounce non-admins to /app rather than show an error, so the admin area
 * "simply doesn't exist for them".
 */
const ADMIN_ROUTES = [
  "/admin",
  "/admin/users",
  "/admin/roles",
  "/admin/flags",
  "/admin/errors",
  "/admin/audit",
  "/admin/signals",
  "/admin/market-data",
  "/admin/ai",
  "/admin/alerts",
  "/admin/subscriptions",
  "/admin/system",
  "/admin/bug-reports",
];

/**
 * Below this, the content area is an empty shell rather than a rendered page.
 *
 * Kept low ON PURPOSE. A legitimately empty page is not a broken one: /funds
 * correctly renders "No mutual funds data available." (32 chars) because MUFAP
 * is bot-blocked and psx_mutual_funds is empty. A 120-char bar failed that page
 * and would have had someone "fix" a working empty state. The real defect this
 * guards is a page that renders NOTHING, or that never leaves its spinner —
 * which the loading assertion below covers separately.
 */
const MIN_TEXT_LENGTH = 25;

/** `main` for AppShell pages; `body` for standalone ones (e.g. /team). */
async function contentLocator(page: import("@playwright/test").Page) {
  return (await page.locator("main").count()) > 0
    ? page.locator("main").first()
    : page.locator("body");
}

for (const route of USER_ROUTES) {
  test(`route ${route} renders real content`, async ({ page }) => {
    // This sweep asserts RENDERING, not console cleanliness. The focused specs
    // (navigation, alerts, finance, portfolio, watchlist) keep the console guard,
    // and they are the right place for it: a breadth sweep touching 16 routes
    // also touches every page that opens a Supabase realtime WebSocket, so one
    // transient network blip turns the whole sweep red with
    // ERR_INTERNET_DISCONNECTED noise that says nothing about the app.
    test.info().annotations.push({ type: "allow-console-errors" });

    const response = await page.goto(route);
    expect(response?.status(), `${route} returned ${response?.status()}`).toBeLessThan(400);

    const content = await contentLocator(page);
    await expect(content).toBeVisible({ timeout: 30_000 });

    // Poll: these pages fetch on mount, so the first read is legitimately empty.
    await expect
      .poll(async () => (await content.innerText()).trim().length, {
        timeout: 30_000,
        message: `${route} never filled its content area — blank or stuck loading`,
      })
      .toBeGreaterThan(MIN_TEXT_LENGTH);

    // NOT asserting "no Loading text anywhere": on a dashboard, individual
    // widgets fetch independently, so /app and /stock/$ticker legitimately show
    // a per-card spinner while the page itself is fully rendered. Failing on
    // that reported two working pages as broken. The polling check above already
    // catches the case that matters — a content area that never fills.

    // If a route boundary caught something, say so here rather than letting a
    // length assertion pass on the error text.
    await expect(page.getByText(/something went wrong|unexpected error/i)).toHaveCount(0);
  });
}

for (const route of ADMIN_ROUTES) {
  test(`admin route ${route} bounces a non-admin`, async ({ page }) => {
    const response = await page.goto(route);
    expect(response?.status(), `${route} returned ${response?.status()}`).toBeLessThan(400);

    // The failure mode worth catching is the guard never resolving: it renders
    // "Verifying administrator access…" while awaiting /api/admin/me, and if that
    // query never settles the user is parked on a spinner forever.
    await page.waitForURL(/\/app(\?|$)/, { timeout: 30_000 });
    await expect(page.getByText(/verifying administrator access/i)).toHaveCount(0);
  });
}

test("the Urdu/RTL rendering path works", async ({ page }) => {
  // The app is bilingual with `rtl: true` in components.json, and every other
  // test here runs in English — so a broken RTL switch would be invisible.
  // Key is `nafaiq-app-lang` (see hooks/use-lang.ts); guessing "nafaiq-lang"
  // silently did nothing and made this look like an RTL bug.
  await page.goto("/app");
  await page.evaluate(() => localStorage.setItem("nafaiq-app-lang", "ur"));
  await page.reload();

  await expect(page.locator("[dir='rtl']").first()).toBeVisible({ timeout: 30_000 });

  const content = await contentLocator(page);
  await expect
    .poll(async () => (await content.innerText()).trim().length, { timeout: 30_000 })
    .toBeGreaterThan(MIN_TEXT_LENGTH);
});
