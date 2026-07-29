import { expect, test } from "../fixtures";

/**
 * J10 — watchlist removal.
 *
 * Removal rather than addition on purpose: "Add Stock" goes through
 * StockSearchBox, which needs /api/symbols, and a journey that is supposed to
 * be deterministic should not depend on the market universe loading. The demo
 * store seeds a watchlist (src/store/watchlist/slice.ts seeds from
 * lib/data.ts WATCHLIST), so removal exercises the same write path with no
 * network at all.
 *
 * Each row's delete control is labelled `Remove {TICKER}`
 * (PsxWatchlistCard.tsx:93), which is the accessible name asserted here — so
 * this doubles as a check that those controls stay screen-reader labelled.
 */
test.describe("watchlist", () => {
  test("seeds a watchlist with labelled remove controls", async ({ page }) => {
    await page.goto("/watchlist");
    await expect(page).toHaveTitle(/Watchlist - NafaIQ/);

    const removeButtons = page.getByRole("button", { name: /^remove /i });
    await expect(removeButtons.first()).toBeVisible();
    expect(await removeButtons.count()).toBeGreaterThan(0);
  });

  test("removing a symbol drops it from the list", async ({ page }) => {
    await page.goto("/watchlist");

    const removeButtons = page.getByRole("button", { name: /^remove /i });
    await expect(removeButtons.first()).toBeVisible();

    const before = await removeButtons.count();
    expect(before, "need at least one seeded symbol to remove").toBeGreaterThan(0);

    // Capture which symbol we are removing so the assertion is about THAT row,
    // not merely about the count going down.
    const label = (await removeButtons.first().getAttribute("aria-label")) ?? "";
    const symbol = label.replace(/^remove\s+/i, "").trim();
    expect(symbol, "could not read the symbol from the remove control").not.toBe("");

    await removeButtons.first().click();

    await expect(removeButtons).toHaveCount(before - 1);
    await expect(
      page.getByRole("button", { name: new RegExp(`^remove ${symbol}$`, "i") }),
    ).toHaveCount(0);
  });

  test("removals accumulate rather than resetting between actions", async ({ page }) => {
    await page.goto("/watchlist");

    const removeButtons = page.getByRole("button", { name: /^remove /i });
    await expect(removeButtons.first()).toBeVisible();

    const before = await removeButtons.count();
    test.skip(before < 2, "needs at least two seeded symbols");

    await removeButtons.first().click();
    await expect(removeButtons).toHaveCount(before - 1);
    await removeButtons.first().click();

    await expect(removeButtons).toHaveCount(before - 2);
  });
});
