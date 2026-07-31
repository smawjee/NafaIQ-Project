import { expect, test } from "../fixtures";

/**
 * J11 — stock price alerts.
 *
 * There was no alerts spec at all, which is how the screen shipped able to
 * alert on exactly four hardcoded symbols (`HBL, ENGRO, LUCK, OGDC`) and two of
 * the backend's nine conditions without anything failing. The gap this closes is
 * not "does the API work" — that is covered by backend tests — it is "can a user
 * actually express the alert they want".
 *
 * Runs on the demo/local path, so these assert the FORM's capability rather than
 * server-side firing: creating a real alert would need a live account and a
 * 60-second evaluator tick, neither of which belongs in a deterministic e2e run.
 */
/**
 * Wait until the page is actually INTERACTIVE, not merely painted.
 *
 * /alerts is server-rendered, so the form markup exists (and a controlled
 * <select> even accepts a native value change) before React has hydrated and
 * attached its onChange handlers. Acting too early therefore "works" on the DOM
 * and silently does nothing to React state — which is exactly how these tests
 * first failed: the select's value changed while the threshold label stayed on
 * the previous condition.
 *
 * The symbol picker is the honest signal: it is disabled until
 * `usePsxSymbols()` resolves, which can only happen once React is running.
 */
async function waitForFormReady(page: import("@playwright/test").Page) {
  const picker = page.getByRole("combobox", { name: /search stock symbol/i });
  await expect(picker).toBeEnabled({ timeout: 30_000 });
  return picker;
}

test.describe("alerts", () => {
  test("the alerts page offers every alert type", async ({ page }) => {
    await page.goto("/alerts");

    for (const label of ["Stock Price", "Bill Reminder", "Budget", "Goal Milestone"]) {
      await expect(page.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
  });

  test("the symbol picker searches the whole market, not a hardcoded list", async ({
    page,
  }) => {
    await page.goto("/alerts");
    const picker = await waitForFormReady(page);

    // MARI is deliberately NOT one of the four symbols the old hardcoded
    // STOCKS array allowed. If this passes, the picker is reading /api/symbols.
    await picker.click();
    await picker.fill("MARI");

    const option = page.getByRole("option", { name: /^MARI/ });
    await expect(option.first()).toBeVisible();
    await option.first().click();

    await expect(picker).toHaveValue("MARI");
  });

  test("exposes all nine conditions, not just above/below", async ({ page }) => {
    await page.goto("/alerts");

    const condition = page.getByRole("combobox", { name: /alert condition/i });
    await expect(condition).toBeVisible();

    const values = await condition.locator("option").evaluateAll((opts) =>
      opts.map((o) => (o as HTMLOptionElement).value),
    );

    expect(values).toEqual(
      expect.arrayContaining([
        "above",
        "below",
        "cross_above",
        "cross_below",
        "pct_change_above",
        "pct_change_below",
        "volume_spike",
        "high_52w",
        "low_52w",
      ]),
    );
  });

  test("the threshold unit follows the chosen condition", async ({ page }) => {
    await page.goto("/alerts");
    await waitForFormReady(page);

    const condition = page.getByRole("combobox", { name: /alert condition/i });

    // A price level is in rupees...
    await condition.selectOption("above");
    await expect(page.getByRole("textbox", { name: /threshold \(PKR\)/i })).toBeVisible();

    // ...a percent move is not, and a volume spike is a multiple. A single box
    // labelled "Price" for all three is how a 3x volume alert becomes "PKR 3".
    await condition.selectOption("pct_change_above");
    await expect(page.getByRole("textbox", { name: /threshold \(%\)/i })).toBeVisible();

    await condition.selectOption("volume_spike");
    await expect(page.getByRole("textbox", { name: /threshold \(×\)/i })).toBeVisible();
  });

  test("52-week conditions hide the threshold input entirely", async ({ page }) => {
    await page.goto("/alerts");
    await waitForFormReady(page);

    const condition = page.getByRole("combobox", { name: /alert condition/i });
    await condition.selectOption("high_52w");

    // The extreme itself is the trigger — there is nothing to type, so showing
    // an empty box only raises the question of what belongs in it.
    await expect(page.getByRole("textbox", { name: /^threshold/i })).toHaveCount(0);
  });

  test("refuses to create an alert with no symbol chosen", async ({ page }) => {
    await page.goto("/alerts");
    await waitForFormReady(page);

    // The symbol no longer defaults to HBL, so creating without picking one has
    // to be an error rather than a silent alert on someone else's stock.
    await page.getByRole("combobox", { name: /alert condition/i }).selectOption("above");
    await page.getByRole("textbox", { name: /threshold \(PKR\)/i }).fill("302");
    await page.getByRole("button", { name: /create alert/i }).click();

    await expect(page.getByText(/please choose a stock/i)).toBeVisible();
  });

  test("creates the user's headline case: HBL above 302", async ({ page }) => {
    await page.goto("/alerts");
    const picker = await waitForFormReady(page);

    await picker.click();
    await picker.fill("HBL");
    await page.getByRole("option", { name: /^HBL/ }).first().click();

    await page.getByRole("combobox", { name: /alert condition/i }).selectOption("above");
    await page.getByRole("textbox", { name: /threshold \(PKR\)/i }).fill("302");
    await page.getByRole("button", { name: /create alert/i }).click();

    // The created alert must state the threshold it was armed with — an alert
    // list that does not show the number is unauditable.
    await expect(page.getByText(/HBL.*302/i).first()).toBeVisible();
  });
});
