import { expect, test } from "../fixtures";

/**
 * J8 — portfolio holding removal.
 *
 * Removal rather than addition: "Add Holding" goes through StockSearchBox,
 * which needs /api/symbols, and these journeys are meant to be deterministic.
 * The demo store seeds holdings, so removal exercises the write path with no
 * network.
 *
 * The interesting part is that removal is deliberately a TWO-STEP choice
 * (PortfolioRemoveHoldingModal.tsx): "I sold it" records a sale and books the
 * proceeds as income, while "Just remove it" undoes the purchase and books
 * nothing. Collapsing those into one button would silently corrupt a user's
 * income figures, so the fork is asserted here rather than just the outcome.
 */
test.describe("portfolio holdings", () => {
  test("lists holdings with labelled edit and delete controls", async ({ page }) => {
    await page.goto("/portfolio");
    await expect(page).toHaveTitle(/Portfolio — NafaIQ/);

    const deletes = page.getByRole("button", { name: /^delete$/i });
    await expect(deletes.first()).toBeVisible();
    await expect(page.getByRole("button", { name: /^edit$/i }).first()).toBeVisible();
  });

  test("deleting asks how, rather than removing immediately", async ({ page }) => {
    await page.goto("/portfolio");

    const deletes = page.getByRole("button", { name: /^delete$/i });
    await expect(deletes.first()).toBeVisible();
    const before = await deletes.count();

    await deletes.first().click();

    // Both paths must be offered — the destructive one must not be the only
    // option, and it must not have already run.
    await expect(page.getByRole("button", { name: /i sold it/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /just remove it/i })).toBeVisible();
    expect(await deletes.count(), "nothing should be removed before choosing").toBe(before);
  });

  test('"Just remove it" drops the holding from the table', async ({ page }) => {
    await page.goto("/portfolio");

    const deletes = page.getByRole("button", { name: /^delete$/i });
    await expect(deletes.first()).toBeVisible();
    const before = await deletes.count();
    expect(before, "need at least one seeded holding").toBeGreaterThan(0);

    await deletes.first().click();
    await page.getByRole("button", { name: /just remove it/i }).click();

    await expect(deletes).toHaveCount(before - 1);
  });

  test('"I sold it" opens the sale form instead of deleting', async ({ page }) => {
    await page.goto("/portfolio");

    const deletes = page.getByRole("button", { name: /^delete$/i });
    await expect(deletes.first()).toBeVisible();
    const before = await deletes.count();

    await deletes.first().click();
    await page.getByRole("button", { name: /i sold it/i }).click();

    // Still on a form, and the holding is untouched until the sale is recorded.
    await expect(page.getByRole("button", { name: /just remove it/i })).toHaveCount(0);
    expect(await deletes.count()).toBe(before);
  });
});
