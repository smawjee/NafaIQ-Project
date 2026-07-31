import { authSettled, expect, test } from "../fixtures";

/**
 * Finance beyond the transaction-add journey already covered by
 * finance-crud.spec.ts: income entries, edit/delete, and the Budgets, Bills
 * and Goals tabs (workbook TC-FIN-02/06/07/09/10/15/16/17/19/20/22/23/24/25).
 *
 * All demo writes stay in Redux (Transactions.tsx / Budgets.tsx / Bills.tsx /
 * Goals.tsx each branch on isDemo before their mutation), so every journey
 * here is deterministic and network-free.
 *
 * NOT covered on purpose:
 *  - "Delete all" for transactions/budgets/bills/goals — the DeleteAllButton
 *    is rendered only for a signed-in NON-demo user (count is forced to 0 in
 *    demo), so the control does not exist in this suite's session.
 *  - Per-budget edit/delete — no such controls exist in the UI (the reducers
 *    exist but nothing dispatches them).
 */

const tab = (page: import("@playwright/test").Page, name: RegExp) =>
  page.getByRole("button", { name }).first();

async function openFinance(page: import("@playwright/test").Page) {
  await page.goto("/finance");
  await expect(page).toHaveTitle(/Finance — NafaIQ/);
  await authSettled(page);
}

test.describe("finance transactions (income / edit / delete)", () => {
  test("adds an income transaction and it appears in the list", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^transactions$/i).click();

    await page.getByRole("button", { name: /add transaction/i }).first().click();
    // The type toggle defaults to Expense; Income hides the category select.
    await page.getByRole("button", { name: /^income$/i }).click();
    const merchant = page.getByPlaceholder(/merchant \/ description/i);
    await merchant.fill("E2E Salary Test");
    await page.getByPlaceholder(/amount \(pkr\)/i).fill("5000");
    await page.getByRole("button", { name: /^add transaction$/i }).last().click();

    await expect(merchant).toHaveCount(0);
    await expect(page.getByText("E2E Salary Test").first()).toBeVisible();
  });

  test("edits an existing transaction in place", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^transactions$/i).click();

    await page.getByRole("button", { name: /^edit transaction$/i }).first().click();
    const merchant = page.getByPlaceholder(/merchant \/ description/i);
    await merchant.fill("E2E Edited Merchant");
    await page.getByRole("button", { name: /save changes/i }).click();

    await expect(merchant).toHaveCount(0);
    await expect(page.getByText("E2E Edited Merchant").first()).toBeVisible();
  });

  test("deletes a single transaction after an explicit confirm", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^transactions$/i).click();

    const deletes = page.getByRole("button", { name: /^delete$/i });
    await expect(deletes.first()).toBeVisible();
    const before = await deletes.count();
    expect(before, "the demo store seeds transactions").toBeGreaterThan(1);

    await deletes.first().click();
    // Deletion must be gated behind a confirm — a stray tap must not destroy data.
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: /^delete transaction$/i }).click();

    await expect(deletes).toHaveCount(before - 1);
    // The rest of the ledger is untouched.
    await expect(page.getByText(/Netflix/).first()).toBeVisible();
  });
});

test.describe("finance budgets", () => {
  test("creates a budget for a new category", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^budgets$/i).click();

    await page.getByRole("button", { name: /^add budget$/i }).first().click();
    // "Savings" is a valid category with no seeded budget.
    await page.getByLabel(/budget category/i).selectOption("Savings");
    await page.getByPlaceholder(/limit amount \(pkr\)/i).fill("15000");
    await page.getByRole("button", { name: /^add budget$/i }).last().click();

    await expect(page.getByText("Savings", { exact: true }).first()).toBeVisible();
  });

  test("rejects a negative budget limit instead of saving it", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^budgets$/i).click();

    await page.getByRole("button", { name: /^add budget$/i }).first().click();
    await page.getByPlaceholder(/limit amount \(pkr\)/i).fill("-1000");
    await page.getByRole("button", { name: /^add budget$/i }).last().click();

    await expect(page.getByText(/please enter a valid limit/i)).toBeVisible();
  });

  test("month navigation moves the displayed month", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^budgets$/i).click();

    // The label between the arrows is "<Month> <Year>", e.g. "July 2026".
    const label = page.getByText(/^[A-Z][a-z]+ \d{4}$/);
    await expect(label).toBeVisible();
    const before = await label.textContent();

    await page.getByRole("button", { name: /‹/ }).click();
    await expect(label).not.toHaveText(before ?? "");
  });
});

test.describe("finance bills", () => {
  test("adds a bill with a due date and it appears in the list", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^bills$/i).click();

    await page.getByRole("button", { name: /^add bill$/i }).first().click();
    await page.getByPlaceholder(/bill name/i).fill("E2E Electricity Bill");
    await page.getByPlaceholder(/amount \(pkr\)/i).fill("6500");
    await page.locator('input[type="date"]').fill("2026-08-05");
    await page.getByRole("button", { name: /^add bill$/i }).last().click();

    await expect(page.getByText("E2E Electricity Bill").first()).toBeVisible();
    // A real date input renders as a real due label (seeded demo bills carry
    // pre-formatted strings and show "Invalid Date" — a known cosmetic bug).
    await expect(page.getByText(/Due Aug 5/).first()).toBeVisible();
  });

  test("rejects a bill with no valid amount", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^bills$/i).click();

    await page.getByRole("button", { name: /^add bill$/i }).first().click();
    await page.getByPlaceholder(/bill name/i).fill("E2E Zero Bill");
    await page.getByPlaceholder(/amount \(pkr\)/i).fill("0");
    await page.getByRole("button", { name: /^add bill$/i }).last().click();

    await expect(page.getByText(/please enter a valid amount/i)).toBeVisible();
    await expect(page.getByText("E2E Zero Bill")).toHaveCount(0);
  });

  test("marking a bill paid books it as an expense transaction", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^bills$/i).click();

    // Demo semantics (store/finance/slice.ts markBillPaid): the bill row is
    // REMOVED and an expense transaction for it is unshifted into the ledger.
    await expect(page.getByText("SNGPL Gas").first()).toBeVisible();
    await page.getByRole("button", { name: /mark as paid/i }).first().click();
    await expect(page.getByText("SNGPL Gas")).toHaveCount(0);

    await tab(page, /^transactions$/i).click();
    await expect(page.getByText("SNGPL Gas").first()).toBeVisible();
  });

  test("deletes a single bill after an explicit confirm", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^bills$/i).click();

    await expect(page.getByText("PTCL Internet").first()).toBeVisible();
    const deletes = page.getByRole("button", { name: /^delete$/i });
    const before = await deletes.count();
    expect(before, "the demo store seeds bills").toBeGreaterThan(1);

    await deletes.first().click();
    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: /^delete bill$/i }).click();

    await expect(deletes).toHaveCount(before - 1);
  });
});

test.describe("finance goals", () => {
  test("creates a savings goal starting at zero progress", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^goals$/i).click();

    await page.getByRole("button", { name: /^add goal$/i }).first().click();
    await page.getByPlaceholder(/^goal name$/i).fill("E2E Test Goal");
    await page.getByPlaceholder(/target amount \(pkr\)/i).fill("200000");
    await page.getByRole("button", { name: /^add goal$/i }).last().click();

    await expect(page.getByText("E2E Test Goal").first()).toBeVisible();
  });

  test("rejects a goal with a non-positive target", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^goals$/i).click();

    await page.getByRole("button", { name: /^add goal$/i }).first().click();
    await page.getByPlaceholder(/^goal name$/i).fill("E2E Bad Goal");
    await page.getByPlaceholder(/target amount \(pkr\)/i).fill("-5000");
    await page.getByRole("button", { name: /^add goal$/i }).last().click();

    await expect(page.getByText(/please enter a valid target amount/i)).toBeVisible();
    await expect(page.getByText("E2E Bad Goal")).toHaveCount(0);
  });

  test("a contribution is booked as a Savings transfer transaction", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^goals$/i).click();

    // Second seeded goal is "Emergency Fund"; its contribution also unshifts a
    // "<Goal> Transfer" transaction (store/finance/slice.ts contributeToGoal),
    // which is the cross-tab proof the money actually moved.
    await expect(page.getByText("Emergency Fund").first()).toBeVisible();
    await page.getByRole("button", { name: /^add contribution$/i }).nth(1).click();
    await page.getByPlaceholder(/amount \(pkr\)/i).fill("10000");
    await page.getByRole("button", { name: /^add contribution$/i }).last().click();

    await tab(page, /^transactions$/i).click();
    await expect(page.getByText("Emergency Fund Transfer").first()).toBeVisible();
  });

  test("deletes a single goal after an explicit confirm", async ({ page }) => {
    await openFinance(page);
    await tab(page, /^goals$/i).click();

    await expect(page.getByText("Umrah 2026").first()).toBeVisible();
    await page.getByRole("button", { name: /^delete goal$/i }).last().click();

    const dialog = page.getByRole("alertdialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: /^delete goal$/i }).click();

    await expect(page.getByText("Umrah 2026")).toHaveCount(0);
    // Only that goal is gone.
    await expect(page.getByText("Hajj Fund").first()).toBeVisible();
  });
});
