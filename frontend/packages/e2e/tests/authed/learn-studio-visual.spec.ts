import type { Page } from "@playwright/test";
import { authSettled, expect, test } from "../fixtures";

const PROJECT_ID = "visual-generated";

const lesson = {
  id: PROJECT_ID,
  emoji: "📈",
  title: "Understanding Dividend Yield",
  subtitle: "Learn how cash income is measured for PSX shares.",
  category: "PSX Learning",
  accent: "#00d4aa",
  duration: "4 min",
  level: "Beginner",
  origin: "generated",
  language: "en",
  sources: [
    { sourceId: "source-1", title: "PSX Investor Guide", heading: "Dividends" },
    {
      sourceId: "source-2",
      title: "NafaIQ Dividend Yield",
      heading: "The formula",
    },
  ],
  projectId: PROJECT_ID,
  videoStatus: "not_requested",
  rewardMode: "practice",
  generatedAt: "2026-08-05T00:00:00Z",
  type: "article",
  presets: ["Why can yield change?", "Show another PSX example"],
  sections: [
    {
      id: "meaning",
      heading: "What dividend yield means",
      blocks: [
        {
          type: "p",
          text: "Dividend yield compares annual cash dividends with the current market price of a PSX share.",
        },
        {
          type: "callout",
          kind: "note",
          text: "A high historical yield is not a promise that the next dividend will be paid.",
        },
      ],
    },
    {
      id: "calculation",
      heading: "Calculate and compare",
      blocks: [
        {
          type: "formula",
          lines: ["Dividend Yield =", "(Annual Dividend ÷ Share Price) × 100"],
        },
        {
          type: "table",
          head: ["PSX share", "Annual dividend", "Share price", "Yield"],
          rows: [
            ["Example A", "PKR 16", "PKR 168", "9.52%"],
            ["Example B", "PKR 8", "PKR 125", "6.40%"],
          ],
        },
      ],
    },
  ],
  quiz: Array.from({ length: 5 }, (_, index) => ({
    q: `What is the grounded lesson point ${index + 1}?`,
    options: [
      "Annual dividend relative to price",
      "Daily volume only",
      "Broker fee",
      "Index weight",
    ],
    correct: 0,
    explanation:
      "Dividend yield relates the annual dividend to the current share price.",
  })),
};

const studyPack = {
  lesson,
  notes: [
    "Dividend yield is an income-comparison measure.",
    "Use current price and the most recent annual dividend.",
  ],
  keyTerms: ["Dividend Yield", "Annual Dividend", "Share Price"],
  flashcards: [
    {
      front: "Dividend yield formula",
      back: "Annual dividend divided by price, multiplied by 100.",
    },
    {
      front: "Is a dividend guaranteed?",
      back: "No. A company may reduce or stop dividends.",
    },
  ],
  suggestedTopics: ["Understanding P/E Ratio", "Managing Risk on the PSX"],
};

function project(overrides: Record<string, unknown> = {}) {
  return {
    id: PROJECT_ID,
    topic: "Dividend yield on PSX",
    language: "en",
    level: "beginner",
    targetMinutes: 4,
    status: "ready",
    stage: "ready",
    errorCode: null,
    errorMessage: null,
    bestScore: 0,
    studyPack,
    videoReady: false,
    videoDurationSeconds: null,
    createdAt: "2026-08-05T00:00:00Z",
    ...overrides,
  };
}

async function mockProject(page: Page, payload = project()) {
  await page.route("**/api/admin/me", (route) =>
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Forbidden" }),
    }),
  );
  await page.route("**/api/learn/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true }),
    }),
  );
  await page.route(
    `**/api/learn/studio/projects/${PROJECT_ID}`,
    async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(payload),
        });
        return;
      }
      await route.continue();
    },
  );
  await page.route(
    `**/api/learn/studio/projects/${PROJECT_ID}/quiz-attempts`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ bestScore: 5 }),
      }),
  );
}

async function openGenerated(page: Page) {
  await page.goto(`/learn/generated/${PROJECT_ID}`);
  await authSettled(page);
  await expect(page.getByTestId("lesson-experience")).toBeVisible();
}

test.describe("LearnHub Studio native visual contract", () => {
  test("official lesson provides the shared visual baseline", async ({
    page,
  }) => {
    test.skip(test.info().project.name !== "authed-chromium");
    await page.route("**/api/admin/me", (route) =>
      route.fulfill({
        status: 403,
        contentType: "application/json",
        body: "{}",
      }),
    );
    await page.route("**/api/learn/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true }),
      }),
    );
    await page.goto("/learn/lesson/candlestick");
    await authSettled(page);

    const experience = page.getByTestId("lesson-experience");
    await expect(experience.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(experience).toHaveScreenshot("official-reading-baseline.png", {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
    });
  });

  test("generated reading view matches the native shell without XP claims", async ({
    page,
  }) => {
    await mockProject(page);
    await openGenerated(page);

    const experience = page.getByTestId("lesson-experience");
    await expect(
      experience.getByRole("heading", { name: lesson.title }),
    ).toBeVisible();
    await expect(
      experience.getByText("AI-generated · Source grounded"),
    ).toBeVisible();
    await expect(
      experience.getByRole("region", { name: "Sources used" }),
    ).toBeVisible();
    await expect(experience.getByText("Practice only")).toBeVisible();
    await expect(experience.getByText(/Up to 50 XP/)).toHaveCount(0);
    await expect(experience).toHaveScreenshot("generated-reading.png", {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
    });
  });

  test("desktop panels remain usable when collapsed and at 125% zoom", async ({
    page,
  }) => {
    test.skip(test.info().project.name !== "authed-chromium");
    await mockProject(page);
    await openGenerated(page);

    await page
      .getByRole("button", { name: "Collapse table of contents" })
      .click();
    await expect(
      page.getByRole("button", { name: "Show table of contents" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Collapse AI Tutor panel" }).click();
    await expect(
      page.getByRole("button", { name: "Open AI tutor" }),
    ).toBeVisible();

    await page.evaluate(() => {
      document.documentElement.style.zoom = "1.25";
    });
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
  });

  test("practice quiz covers wrong feedback, results, retake, and persistence", async ({
    page,
  }) => {
    await mockProject(page);
    await openGenerated(page);
    await page.getByRole("button", { name: /take the quiz/i }).click();

    await expect(page.getByText("Practice Quiz")).toBeVisible();
    await expect(page.getByText(/Up to 50 XP/)).toHaveCount(0);
    await page.getByRole("button", { name: /Daily volume only/ }).click();
    await expect(page.getByText("Explanation")).toBeVisible();
    await expect(page.getByText(/Dividend yield relates/)).toBeVisible();

    for (let index = 0; index < 5; index += 1) {
      const seeResults = page.getByRole("button", { name: /see results/i });
      if (await seeResults.isVisible().catch(() => false)) {
        await seeResults.click();
        break;
      }
      await page.getByRole("button", { name: /next question/i }).click();
      await page
        .getByRole("button", { name: /Annual dividend relative to price/ })
        .click();
    }

    await expect(
      page.getByRole("heading", { name: /quiz results/i }),
    ).toBeVisible();
    await expect(page.getByText(/\+\d+\s*XP/i)).toHaveCount(0);
    await expect(page.getByText(/XP total/i)).toHaveCount(0);
    await expect(page.getByText(/Added to your profile/i)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /retake/i })).toBeVisible();
  });

  test("flashcards expose modal semantics and restore focus", async ({
    page,
  }) => {
    await mockProject(page);
    await openGenerated(page);

    const trigger = page.getByRole("button", { name: "Study flashcards" });
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Flashcards" });
    await expect(dialog).toBeVisible();
    await expect(page.getByRole("button", { name: "Close" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("generation and refusal states remain inside the LearnHub visual system", async ({
    page,
  }) => {
    await mockProject(
      page,
      project({ status: "generating", stage: "validating", studyPack: null }),
    );
    await page.goto(`/learn/generated/${PROJECT_ID}`);
    await authSettled(page);
    await expect(page.getByRole("status")).toContainText(
      "Checking grounding and citations",
    );

    await page.unroute(`**/api/learn/studio/projects/${PROJECT_ID}`);
    await mockProject(
      page,
      project({
        status: "unsupported",
        stage: "unsupported",
        studyPack: null,
        errorMessage: "This topic is outside the approved PSX source corpus.",
      }),
    );
    await page.reload();
    await authSettled(page);
    await expect(
      page.getByRole("heading", { name: /better sources/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/outside the approved PSX source corpus/i),
    ).toBeVisible();
  });

  test("video generation, failure, and ready playback use the native lesson shell", async ({
    page,
  }) => {
    await mockProject(page, project({ stage: "rendering" }));
    await openGenerated(page);
    await expect(page.getByRole("status")).toContainText(
      "Rendering your video",
    );
    await expect(
      page.getByRole("button", { name: /generating video/i }),
    ).toBeDisabled();

    await page.unroute(`**/api/learn/studio/projects/${PROJECT_ID}`);
    await mockProject(
      page,
      project({
        stage: "video_failed",
        errorMessage: "The lesson is ready, but video rendering failed.",
      }),
    );
    await page.reload();
    await authSettled(page);
    await expect(page.getByRole("alert")).toContainText(
      "video rendering failed",
    );

    await page.unroute(`**/api/learn/studio/projects/${PROJECT_ID}`);
    await mockProject(
      page,
      project({ stage: "ready", videoReady: true, videoDurationSeconds: 193 }),
    );
    await page.route(
      `**/api/learn/studio/projects/${PROJECT_ID}/video/playback`,
      (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            url: "/e2e-media/lesson.mp4",
            captionsUrl: "/e2e-media/lesson.vtt",
            posterUrl: "/e2e-media/poster.png",
            durationSeconds: 193,
            expiresIn: 900,
          }),
        }),
    );
    await page.route("**/e2e-media/**", (route) =>
      route.fulfill({ status: 204, body: "" }),
    );
    await page.reload();
    await authSettled(page);
    await expect(
      page.getByRole("button", { name: /article version/i }),
    ).toBeVisible();
    await expect(page.getByText("Practice only")).toBeVisible();
  });

  test("practice quiz records the timed-out state", async ({ page }) => {
    await mockProject(page);
    await openGenerated(page);
    await page.clock.install();
    await page.getByRole("button", { name: /take the quiz/i }).click();
    await page.clock.runFor(31_000);
    await expect(page.getByText("Explanation")).toBeVisible();
    await expect(page.getByText("0 correct so far")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Annual dividend relative to price/ }),
    ).toBeDisabled();
  });

  test("Urdu content uses RTL without overflow", async ({ page }) => {
    const urduLesson = {
      ...lesson,
      title: "پی ایس ایکس میں ڈیویڈنڈ ییلڈ",
      subtitle: "حصص سے حاصل ہونے والی نقد آمدنی کو سمجھیں۔",
      language: "ur",
      sections: [
        {
          id: "urdu-meaning",
          heading: "ڈیویڈنڈ ییلڈ کیا ہے؟",
          blocks: [
            {
              type: "p",
              text: "ڈیویڈنڈ ییلڈ سالانہ نقد منافع کو موجودہ شیئر پرائس کے ساتھ موازنہ کرتی ہے۔ PSX اور P/E جیسے مالی الفاظ اپنی مانوس شکل میں رہتے ہیں۔",
            },
          ],
        },
      ],
    };
    await page.addInitScript(() =>
      localStorage.setItem("nafaiq-app-lang", "ur"),
    );
    await mockProject(
      page,
      project({
        language: "ur",
        studyPack: { ...studyPack, lesson: urduLesson },
      }),
    );
    await openGenerated(page);

    await expect(page.locator('[dir="rtl"]').first()).toBeVisible();
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    await expect(page.getByTestId("lesson-experience")).toHaveScreenshot(
      "generated-urdu-reading.png",
      { animations: "disabled", maxDiffPixelRatio: 0.01 },
    );
  });
});
