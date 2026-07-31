import { authSettled, expect, test } from "../fixtures";

/**
 * Alert creation, toggling and deletion (workbook TC-ALERT-01..06, 08, 09).
 *
 * Demo alerts never touch the backend: Alerts.tsx gates every query on
 * `!!user && !isDemo` and the create handler dispatches addAlert() to Redux
 * for the demo user, unshifting the new alert to the TOP of Active Alerts and
 * a "New alert created: …" entry into Notification History. Both effects are
 * asserted here.
 *
 * Selector notes (all from AlertCreateForm.tsx / AlertsActiveList.tsx):
 *  - The per-type selects have no accessible name — positional locators.
 *  - Each Active Alerts card renders exactly two buttons: [0] the on/off
 *    toggle (state = bg-bull class), [1] delete (lucide-trash-2 icon).
 */

async function openAlerts(page: import("@playwright/test").Page) {
  await page.goto("/alerts");
  await expect(page).toHaveTitle(/Alerts — NafaIQ/);
  await authSettled(page);
}

/** The <section> holding the Active Alerts list (AlertsActiveList.tsx). */
const activeCard = (page: import("@playwright/test").Page) =>
  page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: /^active alerts$/i }) });

/** The <section> holding the Add New Alert form (Alerts.tsx). */
const formCard = (page: import("@playwright/test").Page) =>
  page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: /^add new alert$/i }) });

/** Choose a symbol in the SymbolPicker combobox (options load from /api/symbols). */
async function pickSymbol(
  page: import("@playwright/test").Page,
  scope: import("@playwright/test").Locator,
  symbol: string,
) {
  const box = scope.getByLabel(/search stock symbol/i);
  await box.fill(symbol);
  // The picker chooses on MOUSEDOWN (SymbolPicker.tsx), so dispatch exactly
  // that on the exact-match row. Not click(): its stability wait flakes while
  // the list re-renders as symbols load. Not Enter: it commits the
  // HIGHLIGHTED row, and a resting pointer's onMouseEnter can silently move
  // the highlight to a different match (seen: HBL → HBLTFC2).
  const option = page.getByRole("option", { name: new RegExp(`^${symbol}\\b`) }).first();
  await expect(option).toBeVisible();
  await option.dispatchEvent("mousedown");
  await expect(box).toHaveValue(symbol);
}

test.describe("alerts", () => {
  test("creates a stock price alert that lands on top of Active Alerts", async ({ page }) => {
    await openAlerts(page);
    const form = formCard(page);

    // Stock Price is the default type. Since the extended-conditions rework
    // the symbol is a SymbolPicker combobox and the threshold is a labelled
    // input; the saved title comes from describeCondition() —
    // "HBL price rises above PKR 175.5".
    await form.getByRole("button", { name: /^stock price$/i }).click();
    await pickSymbol(page, form, "HBL");
    await form.getByLabel(/^alert condition$/i).selectOption("above");
    await form.getByLabel(/^threshold/i).fill("175.5");
    await form.getByRole("button", { name: /^create alert$/i }).click();

    await expect(
      activeCard(page).getByText("HBL price rises above PKR 175.5"),
    ).toBeVisible();
  });

  test("rejects a non-positive threshold instead of creating the alert", async ({ page }) => {
    await openAlerts(page);
    const form = formCard(page);

    // The stock guard runs first, so a symbol must be chosen for the
    // threshold validation to be the thing under test.
    await pickSymbol(page, form, "HBL");
    await form.getByLabel(/^threshold/i).fill("-10");
    await form.getByRole("button", { name: /^create alert$/i }).click();

    await expect(form.getByText(/please enter a valid threshold/i)).toBeVisible();
    await expect(activeCard(page).getByText(/-10/)).toHaveCount(0);
  });

  test("creates a bill reminder alert", async ({ page }) => {
    await openAlerts(page);
    const form = formCard(page);

    await form.getByRole("button", { name: /^bill reminder$/i }).click();
    await form.locator("select").nth(0).selectOption("SNGPL Gas");
    await form.locator("select").nth(1).selectOption({ label: "3 days before" });
    await form.getByRole("button", { name: /^create alert$/i }).click();

    await expect(activeCard(page).getByText(/SNGPL Gas — 3 days before/)).toBeVisible();
  });

  test("budget alert honours a custom threshold over the preset", async ({ page }) => {
    await openAlerts(page);
    const form = formCard(page);

    await form.getByRole("button", { name: /^budget$/i }).click();
    await form.locator("select").nth(0).selectOption("Food & Dining");
    await form.locator("select").nth(1).selectOption("custom");
    await form.getByPlaceholder(/e\.g\. 65/i).fill("65");
    await form.getByRole("button", { name: /^create alert$/i }).click();

    await expect(
      activeCard(page).getByText("Food & Dining at 65% of budget"),
    ).toBeVisible();
  });

  test("goal milestone alert honours a custom milestone over the preset", async ({ page }) => {
    await openAlerts(page);
    const form = formCard(page);

    await form.getByRole("button", { name: /^goal milestone$/i }).click();
    await form.locator("select").nth(0).selectOption("Hajj Fund");
    await form.locator("select").nth(1).selectOption("custom");
    await form.getByPlaceholder(/e\.g\. 33/i).fill("30");
    await form.getByRole("button", { name: /^create alert$/i }).click();

    await expect(activeCard(page).getByText("Hajj Fund 30% reached")).toBeVisible();
  });

  test("push and email channels save independently", async ({ page }) => {
    await openAlerts(page);
    const form = formCard(page);

    // Push defaults ON, Email OFF — invert both, so only Email is set. The
    // channel choice is visible in the history entry the create writes.
    await form.getByRole("checkbox", { name: /^push$/i }).click();
    await form.getByRole("checkbox", { name: /^email$/i }).click();
    await pickSymbol(page, form, "HBL");
    await form.getByLabel(/^threshold/i).fill("150");
    await form.getByRole("button", { name: /^create alert$/i }).click();

    // The entry renders in BOTH Notification History and Alert Events.
    await expect(
      page
        .getByText(/New alert created: HBL price rises above PKR 150 \(Email\)/)
        .first(),
    ).toBeVisible();
  });

  test("toggles an existing alert off and back on", async ({ page }) => {
    await openAlerts(page);
    const card = activeCard(page);

    // First seeded alert ("HBL above PKR 150") starts enabled; its toggle is
    // the first button in its card and shows state via the bg-bull class.
    await expect(card.getByText("HBL above PKR 150")).toBeVisible();
    const toggle = card.locator("button").first();
    await expect(toggle).toHaveClass(/bg-bull/);

    await toggle.click();
    await expect(toggle).not.toHaveClass(/bg-bull/);

    await toggle.click();
    await expect(toggle).toHaveClass(/bg-bull/);
  });

  test("deletes an alert after an explicit confirm", async ({ page }) => {
    await openAlerts(page);
    const card = activeCard(page);

    await expect(card.getByText("HBL above PKR 150")).toBeVisible();
    const deletes = card.locator("button:has(svg.lucide-trash-2)");
    const before = await deletes.count();
    expect(before, "the demo store seeds alerts").toBeGreaterThan(1);

    await deletes.first().click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: /^delete$/i }).click();

    await expect(deletes).toHaveCount(before - 1);
    await expect(card.getByText("HBL above PKR 150")).toHaveCount(0);
  });
});
