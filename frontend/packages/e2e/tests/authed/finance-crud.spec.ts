import { expect, test } from "../fixtures";

/**
 * J9 — the finance transaction lifecycle.
 *
 * This is the journey the navigation specs cannot cover: it asserts a STATE
 * CHANGE, not that a page rendered. A title assertion catches "the route is
 * broken"; it never catches "the transaction saves but the total stops moving".
 *
 * Deterministic without any stubbing: the demo account's writes stay in the
 * Redux store and never reach the backend (src/lib/demo.ts — "all of its app
 * activity lives in the local Redux store and must never reach the backend"),
 * so there is no network, no market-hours dependency and no HAR.
 */

const MERCHANT = "E2E Test Merchant";
const AMOUNT = "1234";

async function openFinance(page: import("@playwright/test").Page) {
  await page.goto("/finance");
  await expect(page).toHaveTitle(/Finance — NafaIQ/);
  // The tabs are the top-level nav within the feature; Transactions is where
  // the add affordance lives.
  const tab = page.getByRole("button", { name: /^transactions$/i }).first();
  if (await tab.isVisible().catch(() => false)) await tab.click();
}

test.describe("finance transactions", () => {
  test("adds a transaction and it appears in the list", async ({ page }) => {
    await openFinance(page);

    // Baseline BEFORE the write. Asserting a delta is what stops this passing
    // spuriously — a bare "merchant is visible" would also be satisfied by the
    // text sitting in the still-open dialog.
    const before = await page.getByText(MERCHANT).count();
    expect(before, "the fixture merchant should not exist yet").toBe(0);

    await page.getByRole("button", { name: /add transaction/i }).first().click();

    const merchantField = page.getByPlaceholder(/merchant \/ description/i);
    await merchantField.fill(MERCHANT);
    await page.getByPlaceholder(/amount \(pkr\)/i).fill(AMOUNT);

    // Submit is the dialog's own "Add Transaction", not the FAB that opened it.
    await page.getByRole("button", { name: /^add transaction$/i }).last().click();

    // The dialog must close first, otherwise the assertion below could be
    // reading the form we just typed into rather than a committed row.
    await expect(merchantField).toHaveCount(0);
    await expect(page.getByText(MERCHANT).first()).toBeVisible();
  });

  test("the new transaction is findable by search", async ({ page }) => {
    await openFinance(page);

    await page.getByRole("button", { name: /add transaction/i }).first().click();
    await page.getByPlaceholder(/merchant \/ description/i).fill(MERCHANT);
    await page.getByPlaceholder(/amount \(pkr\)/i).fill(AMOUNT);
    await page.getByRole("button", { name: /^add transaction$/i }).last().click();
    await expect(page.getByText(MERCHANT).first()).toBeVisible();

    // Search is what makes a long ledger usable; it reads the same store the
    // write went into, so this proves the row really landed there.
    await page.getByPlaceholder(/search transactions/i).fill(MERCHANT);

    await expect(page.getByText(MERCHANT).first()).toBeVisible();
  });

  test("a search with no matches does not show the new transaction", async ({ page }) => {
    await openFinance(page);

    await page.getByRole("button", { name: /add transaction/i }).first().click();
    await page.getByPlaceholder(/merchant \/ description/i).fill(MERCHANT);
    await page.getByPlaceholder(/amount \(pkr\)/i).fill(AMOUNT);
    await page.getByRole("button", { name: /^add transaction$/i }).last().click();
    await expect(page.getByText(MERCHANT).first()).toBeVisible();

    await page.getByPlaceholder(/search transactions/i).fill("zzzz-no-such-merchant");

    await expect(page.getByText(MERCHANT)).toHaveCount(0);
  });

  test("the add dialog rejects an empty amount rather than saving a zero row", async ({
    page,
  }) => {
    await openFinance(page);

    await page.getByRole("button", { name: /add transaction/i }).first().click();
    await page.getByPlaceholder(/merchant \/ description/i).fill("E2E Incomplete");
    // Deliberately no amount.
    await page.getByRole("button", { name: /^add transaction$/i }).last().click();

    // Either the dialog stays open, or nothing was added. Both are acceptable;
    // silently creating a 0-value transaction is not.
    await expect(page.getByText("E2E Incomplete").first()).not.toBeVisible();
  });
});
