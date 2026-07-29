import { authSettled, expect, test } from "../fixtures";

/**
 * AI assistant panel (workbook TC-AI-01/10).
 *
 * The assistant streams from POST /api/assistant/chat, which fixtures.ts
 * stubs with a deterministic SSE body — so these journeys assert the panel's
 * open/compose/stream/history behaviour, not model output.
 *
 * The entry point is the sidebar's "Ask NafaIQ AI" button, and the sidebar is
 * desktop-only (hidden below lg) — the mobile project skips.
 *
 * Action-draft confirm/cancel (TC-AI-02..06) is NOT driven here: the draft
 * card only appears when the stream emits a `draft` frame whose payload the
 * backend owns; that contract is covered by backend tests
 * (test_assistant_agent.py / test_assistant_execute.py).
 */

test.describe("assistant", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(
      testInfo.project.name.includes("mobile"),
      "the assistant entry point lives in the desktop-only sidebar",
    );
  });

  test("answers a typed question", async ({ page }) => {
    await page.goto("/app");
    await authSettled(page);

    await page.getByRole("button", { name: /ask nafaiq ai/i }).click();
    const dialog = page.getByRole("dialog", { name: /ask nafaiq ai/i });
    await expect(dialog).toBeVisible();

    const input = dialog.getByPlaceholder(/ask or tell me what to do/i);
    await input.fill("What is my current net worth?");
    await dialog.getByRole("button", { name: /^send$/i }).click();

    await expect(dialog.getByText("Deterministic e2e answer.").first()).toBeVisible();
  });

  test("keeps the chat history in order within the session", async ({ page }) => {
    await page.goto("/app");
    await authSettled(page);

    await page.getByRole("button", { name: /ask nafaiq ai/i }).click();
    const dialog = page.getByRole("dialog", { name: /ask nafaiq ai/i });
    const input = dialog.getByPlaceholder(/ask or tell me what to do/i);

    await input.fill("First question about spending");
    await input.press("Enter");
    await expect(dialog.getByText("Deterministic e2e answer.").first()).toBeVisible();

    await input.fill("Second question about goals");
    await input.press("Enter");

    // Both user messages remain visible, in the order they were sent.
    await expect(dialog.getByText("First question about spending")).toBeVisible();
    await expect(dialog.getByText("Second question about goals")).toBeVisible();
    const texts = await dialog
      .getByText(/question about (spending|goals)/)
      .allTextContents();
    expect(texts[0]).toContain("First");
  });
});
