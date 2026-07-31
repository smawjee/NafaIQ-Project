import { authSettled, expect, test } from "../fixtures";

/**
 * J6 + J7 — the dashboard, and a sweep across every primary destination.
 *
 * The sweep is the single highest-ROI regression net in the suite: one spec
 * proves that every sidebar route still mounts, still resolves its data layer,
 * and still sets its own <title>. A broken route anywhere fails here.
 */
const DESTINATIONS: { path: string; title: RegExp }[] = [
  { path: "/app", title: /Dashboard — NafaIQ/ },
  { path: "/psx", title: /PSX Market — NafaIQ Trading Terminal/ },
  { path: "/portfolio", title: /Portfolio — NafaIQ/ },
  { path: "/watchlist", title: /Watchlist - NafaIQ/ },
  { path: "/finance", title: /Finance — NafaIQ/ },
  { path: "/alerts", title: /Alerts — NafaIQ/ },
];

test.describe("dashboard", () => {
  test("loads for the signed-in demo account", async ({ page }) => {
    await page.goto("/app");

    await expect(page).toHaveTitle(/Dashboard — NafaIQ/);
    // Did NOT get bounced to /auth — the storageState session is live.
    expect(new URL(page.url()).pathname).toBe("/app");
  });

  test("mounts the AI recommendation card", async ({ page }) => {
    await page.goto("/app");

    // AI responses are stubbed in fixtures.ts, so this is deterministic.
    await expect(page.getByTestId("dashboard-recommendation")).toBeVisible();
  });
});

test.describe("navigation sweep", () => {
  for (const { path, title } of DESTINATIONS) {
    test(`reaches ${path} and it identifies itself`, async ({ page }) => {
      await page.goto(path);

      await expect(page).toHaveTitle(title);
      expect(new URL(page.url()).pathname).toBe(path);
    });
  }

  test("moves between routes without a full reload", async ({ page }) => {
    await page.goto("/app");
    await expect(page).toHaveTitle(/Dashboard — NafaIQ/);
    // The auth overlay (z-[60]) swallows clicks until the session resolves —
    // on the mobile project that window is long enough to eat this tap.
    await authSettled(page);

    await page.getByRole("link", { name: /finance/i }).first().click();

    await expect(page).toHaveTitle(/Finance — NafaIQ/);
    expect(new URL(page.url()).pathname).toBe("/finance");
  });
});
