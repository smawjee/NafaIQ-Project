import { authSettled, expect, test } from "../fixtures";

/**
 * Watchlist ADDITION journeys (workbook TC-WATCH-01/02/04/07/08/09) —
 * the deliberate complement to watchlist-crud.spec.ts, which stays
 * removal-only so it never depends on the network.
 *
 * Addition DOES depend on the network: StockSearchBox filters client-side
 * over GET /api/symbols + /api/market/snapshot, both served by the local
 * uvicorn the suite already boots. Symbol METADATA (the universe) is stable
 * when the market is closed, so searching is deterministic even off-hours;
 * only prices are not, and no price value is asserted here.
 */

async function openWatchlist(page: import("@playwright/test").Page) {
  await page.goto("/watchlist");
  await expect(page).toHaveTitle(/Watchlist - NafaIQ/);
  await authSettled(page);
}

async function openSearch(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: /^add stock$/i }).click();
  // By placeholder, not accessible name: the app HEADER carries a second
  // StockSearchBox with the same aria-label; only the watchlist popover's
  // instance uses this placeholder (PsxWatchlistCard.tsx).
  const box = page.getByPlaceholder(/search stocks to add/i);
  await expect(box).toBeVisible();
  return box;
}

test.describe("watchlist additions", () => {
  test("adds a searched stock and its row appears with a labelled remove control", async ({
    page,
  }) => {
    await openWatchlist(page);
    const box = await openSearch(page);

    await box.fill("PSO");
    const result = page.getByRole("button", { name: /^PSO\b/ }).first();
    await expect(result).toBeVisible();
    await result.click();

    await expect(page.getByText(/PSO added to watchlist/)).toBeVisible();
    await expect(page.getByRole("button", { name: /^remove pso$/i })).toBeVisible();
  });

  test("an unknown symbol yields no results to add", async ({ page }) => {
    await openWatchlist(page);
    const box = await openSearch(page);

    await box.fill("XYZ123");
    await expect(page.getByText(/no stocks found/i)).toBeVisible();
  });

  test("an already-watched symbol cannot be added twice", async ({ page }) => {
    await openWatchlist(page);
    const before = await page.getByRole("button", { name: /^remove /i }).count();

    const box = await openSearch(page);
    await box.fill("HBL");

    // The row for a watched symbol is rendered disabled with an "Added"
    // marker (StockSearchBox mode="add"), so the duplicate path is blocked
    // before any click lands.
    const result = page.getByRole("button", { name: /^HBL\b/ }).first();
    await expect(result).toBeVisible();
    await expect(result).toBeDisabled();
    await expect(result.getByText(/^added$/i)).toBeVisible();

    await expect(page.getByRole("button", { name: /^remove /i })).toHaveCount(before);
  });

  test("clear-all empties the watchlist after an explicit confirm", async ({ page }) => {
    await openWatchlist(page);

    const removes = page.getByRole("button", { name: /^remove /i });
    await expect(removes.first()).toBeVisible();

    await page.getByRole("button", { name: /^delete all$/i }).click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/delete all watchlist symbols\?/i)).toBeVisible();
    await dialog.getByRole("button", { name: /^delete all$/i }).click();

    await expect(removes).toHaveCount(0);
    // The destructive affordance disappears with the last row (count <= 0
    // hides DeleteAllButton) — nothing left to double-fire.
    await expect(page.getByRole("button", { name: /^delete all$/i })).toHaveCount(0);
    // The page is still usable: Add Stock remains the way back.
    await expect(page.getByRole("button", { name: /^add stock$/i })).toBeVisible();
  });

  test("a watchlist row navigates to that stock's detail page", async ({ page }) => {
    await openWatchlist(page);

    const link = page.getByRole("link", { name: /^LUCK\b/ }).first();
    await expect(link).toBeVisible();
    await link.click();

    await expect(page).toHaveTitle(/LUCK/);
    expect(new URL(page.url()).pathname).toBe("/stock/LUCK");
  });
});
