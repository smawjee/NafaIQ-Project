import { expect, test } from "../fixtures";

/**
 * J3 + J4 — the PSX terminal and a stock deep-link.
 *
 * Both are public (AuthGate in src/routes/__root.tsx treats /psx and /stock/*
 * as unauthenticated-allowed).
 *
 * These assert STRUCTURE, never a value: use-psx.ts polls on a 30-120s
 * refetchInterval, and PSX is closed outside 09:30-15:30 PKT, so any
 * price-based expectation is time-of-day dependent.
 */
test.describe("PSX terminal", () => {
  // The title assertion is the only part of /psx that does not depend on live
  // market data, so it is the only part asserted unconditionally.
  test("serves the terminal route", async ({ page }) => {
    await page.goto("/psx");

    await expect(page).toHaveTitle(/PSX Market — NafaIQ Trading Terminal/);
  });

  /**
   * EVERYTHING BELOW IS DATA-DEPENDENT — skipped until the HAR fixture exists.
   *
   * Measured across consecutive runs outside market hours: `psx-chart-card`
   * resolved on one run and was absent on the next, with no code change in
   * between. The card, the toolbar, `psx-chart-plot` (PSX.tsx:494) and the
   * sector heatmap all sit behind data-conditional branches, and the backend
   * has no fresh history to serve when PSX is closed (09:30-15:30 PKT, Mon-Fri).
   *
   * A spec that flips between pass and fail on the wall clock is worse than no
   * spec: it trains the team to ignore red, and it would make the triage skill
   * file and re-file the same phantom bug.
   *
   * To enable: record fixtures/har/psx-market.har DURING market hours, then
   * replay it with context.routeFromHAR in fixtures.ts and delete this skip.
   */
  test.skip("renders the chart card, toolbar, plot and heatmap (needs the market-hours HAR)", async ({
    page,
  }) => {
    await page.goto("/psx");

    const card = page.getByTestId("psx-chart-card");
    await expect(card).toBeVisible();
    await expect(card.getByRole("button").first()).toBeVisible();
    await expect(page.getByTestId("psx-chart-plot")).toBeVisible();
    await expect(page.getByTestId("psx-heatmap-scroll")).toBeVisible();
  });
});

test.describe("stock detail", () => {
  test("opens a symbol by deep link", async ({ page }) => {
    await page.goto("/stock/HBL");

    // stock.$ticker.tsx builds its title from the ticker.
    await expect(page).toHaveTitle(/HBL/);
  });

  test("resolves a lower-case ticker in the URL", async ({ page }) => {
    await page.goto("/stock/hbl");

    // Documents actual behaviour: the route echoes the raw path param into the
    // title, so this renders "hbl — NafaIQ". src/lib/ai/reports-client.ts DOES
    // uppercase the symbol before calling the API, so the two disagree. Cosmetic
    // (and mildly SEO-relevant) rather than functional — the page still loads.
    await expect(page).toHaveTitle(/hbl/i);
  });
});
