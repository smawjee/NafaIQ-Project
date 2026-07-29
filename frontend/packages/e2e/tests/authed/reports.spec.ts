import { authSettled, expect, test } from "../fixtures";

/**
 * AI report journeys (workbook TC-REP-01/02/03/04/07, TC-MKT-11).
 *
 * fixtures.ts stubs every /api/ai/** call with a deterministic report whose
 * headline is "Deterministic e2e report." — so these journeys assert the REAL
 * panel state machine (idle → generating → rendered → regenerate → error →
 * retry) without depending on an LLM. The error path layers a 503 route on
 * top of the stub (last registered route wins), then removes it so retry
 * recovers.
 */

const STUB_HEADLINE = "Deterministic e2e report.";

test.describe("AI reports", () => {
  test("generates the portfolio report and offers regenerate", async ({ page }) => {
    await page.goto("/portfolio");
    await authSettled(page);

    await page.getByRole("button", { name: /^generate report$/i }).click();

    await expect(page.getByText(STUB_HEADLINE).first()).toBeVisible();
    const regen = page.getByRole("button", { name: /^regenerate$/i });
    await expect(regen).toBeVisible();

    // Regenerate goes through the same mutation and re-renders the report.
    await regen.click();
    await expect(page.getByText(STUB_HEADLINE).first()).toBeVisible();
  });

  test("a failed generation shows the error state, and retry recovers", async ({ page }) => {
    // The browser logs the stubbed 503 as a resource error; that noise is the
    // point of this test, not a regression.
    test.info().annotations.push({ type: "allow-console-errors" });

    await page.goto("/portfolio");
    await authSettled(page);

    await page.route("**/api/ai/report/portfolio**", (route) =>
      route.fulfill({ status: 503, contentType: "application/json", body: "{}" }),
    );
    await page.getByRole("button", { name: /^generate report$/i }).click();

    // ReportErrorBanner's `unavailable` branch: message + a Try again button,
    // never a crash or a blank card.
    const retry = page.getByRole("button", { name: /^try again$/i });
    await expect(retry).toBeVisible();

    // Clear the 503 layer; the deterministic stub underneath takes over.
    await page.unroute("**/api/ai/report/portfolio**");
    await retry.click();
    await expect(page.getByText(STUB_HEADLINE).first()).toBeVisible();
  });

  test("the dashboard recommendation renders through the shared report view", async ({
    page,
  }) => {
    await page.goto("/app");
    await authSettled(page);

    const rec = page.getByTestId("dashboard-recommendation");
    await expect(rec).toBeVisible();
    await expect(rec.getByText(STUB_HEADLINE)).toBeVisible();
  });
});
