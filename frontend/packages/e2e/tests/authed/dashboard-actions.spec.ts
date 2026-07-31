import { authSettled, expect, test } from "../fixtures";

/**
 * Dashboard journeys beyond "it loads" (workbook TC-DASH-01/05/06/07/08/09/
 * 10/12/13/14): the greeting, the chart range switcher, all three quick-add
 * flows (each verified on the destination page, not just by the dialog
 * closing), the watchlist strip, goals, and the AI recommendation panel.
 *
 * The demo dashboard runs entirely on showcase/Redux data (Dashboard.tsx
 * useShowcaseDashboard), so no market/API values are asserted — structure and
 * state changes only.
 */

async function openDashboard(page: import("@playwright/test").Page) {
  await page.goto("/app");
  await expect(page).toHaveTitle(/Dashboard — NafaIQ/);
  await authSettled(page);
}

test.describe("dashboard", () => {
  test("greets the user and shows the KSE-100 day line", async ({ page }) => {
    await openDashboard(page);

    await expect(
      page.getByRole("heading", { level: 1 }).filter({ hasText: /Asalam-o-Alaikum,/ }),
    ).toBeVisible();
    // The KSE line renders +x.xx% / -x.xx% or a muted placeholder — the label
    // itself must always be there.
    await expect(page.getByText("KSE-100").first()).toBeVisible();
  });

  test("portfolio chart range buttons switch the active range", async ({ page }) => {
    await openDashboard(page);

    const threeM = page.getByRole("button", { name: "3M", exact: true });
    const oneM = page.getByRole("button", { name: "1M", exact: true });
    await expect(threeM).toBeVisible();

    await threeM.click();
    await expect(threeM).toHaveClass(/bg-bull/);
    await expect(oneM).not.toHaveClass(/bg-bull/);

    await oneM.click();
    await expect(oneM).toHaveClass(/bg-bull/);
  });

  test("quick-add transaction lands in the Finance ledger", async ({ page }) => {
    await openDashboard(page);

    await page.getByRole("button", { name: /^add transaction$/i }).first().click();
    await page.getByPlaceholder(/merchant \/ description/i).fill("E2E Quick Careem");
    await page.getByPlaceholder(/amount \(pkr\)/i).fill("500");
    await page.getByRole("button", { name: /^add transaction$/i }).last().click();
    await expect(page.getByPlaceholder(/merchant \/ description/i)).toHaveCount(0);

    // The write must survive navigation — same Redux store the Finance page reads.
    await page.goto("/finance");
    await authSettled(page);
    await page.getByRole("button", { name: /^transactions$/i }).first().click();
    await expect(page.getByText("E2E Quick Careem").first()).toBeVisible();
  });

  test("quick-add holding lands in the Portfolio table", async ({ page }) => {
    await openDashboard(page);

    await page.getByRole("button", { name: /^add holding$/i }).first().click();
    await page.getByPlaceholder(/stock symbol \(e\.g\. HBL\)/i).fill("MEBL");
    await page.getByPlaceholder(/^shares$/i).fill("50");
    await page.getByPlaceholder(/buy price per share \(pkr\)/i).fill("120");
    await page.getByRole("button", { name: /^add holding$/i }).last().click();
    await expect(page.getByPlaceholder(/^shares$/i)).toHaveCount(0);

    await page.goto("/portfolio");
    await authSettled(page);
    await expect(page.getByText("MEBL").first()).toBeVisible();
  });

  test("quick-add alert lands in Active Alerts", async ({ page }) => {
    await openDashboard(page);

    await page.getByRole("button", { name: /^add alert$/i }).first().click();
    // Scope to the Modal's full-screen overlay, not the inner header row.
    const modal = page
      .locator("div.fixed.inset-0")
      .filter({ has: page.getByRole("heading", { name: /^add alert$/i }) });
    // Since the extended-conditions rework the symbol is a SymbolPicker
    // combobox and the threshold input is labelled. The picker chooses on
    // mousedown; dispatching it on the exact row avoids both the click
    // stability flake and Enter's follow-the-highlight surprise.
    const symbolBox = modal.getByLabel(/search stock symbol/i);
    await symbolBox.fill("ENGRO");
    const engro = page.getByRole("option", { name: /^ENGRO\b/ }).first();
    await expect(engro).toBeVisible();
    await engro.dispatchEvent("mousedown");
    await expect(symbolBox).toHaveValue("ENGRO");
    await modal.getByLabel(/^threshold/i).fill("300");
    await modal.getByRole("button", { name: /^create alert$/i }).click();

    await page.goto("/alerts");
    await authSettled(page);
    await expect(
      page.getByText(/ENGRO price rises above PKR 300/).first(),
    ).toBeVisible();
  });

  test("shows the watchlist strip and the savings goals", async ({ page }) => {
    await openDashboard(page);

    // Seeded demo data: watchlist HBL..FFC, goals led by Hajj Fund.
    await expect(page.getByText("HBL").first()).toBeVisible();
    await expect(page.getByText("Hajj Fund").first()).toBeVisible();
  });

  test("the AI recommendation popup opens and closes", async ({ page }) => {
    await openDashboard(page);

    // The testid element IS the trigger pill; the content lives in a popup
    // dialog it opens (DashboardRecommendation.tsx).
    const rec = page.getByTestId("dashboard-recommendation");
    await expect(rec).toBeVisible();
    await rec.click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: /ai recommendation/i })).toBeVisible();

    await dialog.getByRole("button", { name: /^close$/i }).click();
    await expect(dialog).toHaveCount(0);
  });
});
