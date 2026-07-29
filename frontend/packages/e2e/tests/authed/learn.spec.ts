import { authSettled, expect, test } from "../fixtures";

/**
 * Learn Hub journeys (workbook TC-LEARN-01/03/05/06/09): the hub renders its
 * lessons, a reading lesson renders its article, the quiz can be completed
 * end-to-end to the results screen, flashcards flip and advance, and the AI
 * tutor answers (deterministically — fixtures.ts stubs /api/ai/**, which is
 * where tutor-client.ts streams from).
 *
 * Learn content is static from @nafaiq/shared — no network, no market data.
 */

test.describe("learn hub", () => {
  test("lists lessons and the glossary", async ({ page }) => {
    await page.goto("/learn");
    await authSettled(page);

    await expect(page.getByText(/lessons done/i).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: /^glossary$/i })).toBeVisible();
  });

  test("flashcards flip and advance through the deck", async ({ page }) => {
    await page.goto("/learn");
    await authSettled(page);

    await page.getByRole("button", { name: /^flashcards$/i }).first().click();

    const flip = page.getByRole("button", { name: /flip card/i });
    await expect(flip).toBeVisible();
    await expect(page.getByText(/1 \/ \d+ terms/)).toBeVisible();

    await flip.click();
    await page.getByRole("button", { name: /^got it$/i }).click();
    await expect(page.getByText(/2 \/ \d+ terms/)).toBeVisible();

    await page.getByRole("button", { name: /^close$/i }).click();
    await expect(flip).toHaveCount(0);
  });
});

test.describe("lesson", () => {
  test("a reading lesson renders its article and offers the quiz", async ({ page }) => {
    await page.goto("/learn/lesson/candlestick");
    await authSettled(page);

    await expect(page.locator("article")).toBeVisible();
    expect(await page.locator("article h2").count()).toBeGreaterThan(2);
    await expect(
      page.getByRole("button", { name: /take the quiz/i }),
    ).toBeVisible();
  });

  test("the quiz runs through to the results screen", async ({ page }) => {
    await page.goto("/learn/lesson/candlestick");
    await authSettled(page);

    await page.getByRole("button", { name: /take the quiz/i }).click();

    // Answer every question (option A each time — correctness is not under
    // test, completion is) until "See Results" replaces "Next Question".
    for (let i = 0; i < 10; i++) {
      await page
        .locator("article, main, body")
        .last()
        .getByRole("button")
        .filter({ hasText: /^A/ })
        .first()
        .click();

      const see = page.getByRole("button", { name: /see results/i });
      if (await see.isVisible().catch(() => false)) {
        await see.click();
        break;
      }
      await page.getByRole("button", { name: /next question/i }).click();
    }

    await expect(page.getByRole("heading", { name: /quiz results/i })).toBeVisible();
    await expect(page.getByText(/XP/).first()).toBeVisible();
  });

  test("the lesson AI tutor answers a question", async ({ page }) => {
    await page.goto("/learn/lesson/candlestick");
    await authSettled(page);

    // TWO ChatPanels exist in the DOM: the xl-only right column and the
    // mobile sheet. Open whichever entry point this viewport shows, then talk
    // to the VISIBLE input — .first() can be the hidden column instance.
    const inputs = page.getByPlaceholder(/ask about this lesson/i);
    const visibleInput = () => inputs.filter({ visible: true }).first();
    if (!(await visibleInput().isVisible().catch(() => false))) {
      await page
        .getByRole("button", { name: /open ai tutor|ask ai tutor/i })
        .filter({ visible: true })
        .first()
        .click();
    }
    await expect(visibleInput()).toBeVisible();

    await visibleInput().fill("What does a candlestick wick mean?");
    await visibleInput().press("Enter");

    // The SSE stub in fixtures.ts streams exactly this.
    await expect(page.getByText("Deterministic e2e answer.").first()).toBeVisible();
  });
});
