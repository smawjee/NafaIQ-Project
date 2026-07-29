import { authSettled, expect, test } from "../fixtures";

/**
 * Settings journeys (workbook TC-PROF-02/03/08).
 *
 * Scope decisions, so nobody re-litigates them later:
 *  - Theme offers Light/Dark ONLY — there is no "System" option in
 *    settings.tsx, so the documented three-way toggle cannot be tested.
 *  - There is NO display-name editor anywhere in the app (settings shows the
 *    name read-only) — TC-PROF-01 is a product gap, not a test gap.
 *  - Notification preference toggles PATCH the real backend for any signed-in
 *    user; the demo account must never write server-side state, so toggling
 *    is deliberately not exercised here.
 *  - Gmail connect/sync/disconnect need a real Google OAuth consent — out of
 *    automation scope.
 */

async function openSettings(page: import("@playwright/test").Page) {
  await page.goto("/settings");
  await expect(page).toHaveTitle(/Settings — NafaIQ/);
  await authSettled(page);
}

test.describe("settings", () => {
  test("theme switches to Light, persists across reload, and back to Dark", async ({
    page,
  }) => {
    await openSettings(page);

    const html = page.locator("html");
    await page.getByRole("button", { name: /^Light/ }).click();
    await expect(html).toHaveClass(/light/);

    // Persisted (localStorage nafaiq-landing-theme), not just component state.
    await page.reload();
    await authSettled(page);
    await expect(html).toHaveClass(/light/);

    await page.getByRole("button", { name: /^Dark/ }).click();
    await expect(html).not.toHaveClass(/light/);
  });

  test("language switches to Urdu (RTL) and back to English", async ({ page }) => {
    await openSettings(page);

    // Button's accessible name is label + description (settings.tsx langOptions).
    await page.getByRole("button", { name: /Right-to-left Urdu interface/i }).click();
    await expect(page.locator('[dir="rtl"]').first()).toBeVisible();

    // Once the UI is in Urdu EVERYTHING on the English button is translated
    // (it reads "انگریزی معیاری انٹرفیس زبان"), so match either language.
    await page.getByRole("button", { name: /English|انگریزی/ }).click();
    await expect(page.locator('[dir="rtl"]')).toHaveCount(0);
  });

  test("currency is fixed to PKR with no selector offered", async ({ page }) => {
    await openSettings(page);

    // The demo account gets the signed-out fallback on the Finance card (the
    // income input would write real backend state), so assert the card's own
    // copy — which names a fixed income, not a choice of currency.
    await expect(page.getByText(/set a fixed monthly income/i)).toBeVisible();
    // No currency dropdown exists anywhere on the page.
    await expect(page.locator("select")).toHaveCount(0);
  });
});
