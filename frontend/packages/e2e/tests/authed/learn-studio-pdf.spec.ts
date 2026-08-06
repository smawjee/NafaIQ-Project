import { authSettled, expect, test } from "../fixtures";

const PROJECT_ID = "pdf-upload-project";

test("uploads a private PDF and hydrates the native generation page", async ({
  page,
}) => {
  await page.route("**/api/admin/me", (route) =>
    route.fulfill({ status: 403, contentType: "application/json", body: "{}" }),
  );
  await page.route("**/api/learn/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true }),
    }),
  );
  await page.route("**/api/learn/studio/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        enabled: true,
        packDailyLimit: 5,
        videoDailyLimit: 1,
        pdfEnabled: true,
        pdfMaxBytes: 15 * 1024 * 1024,
        pdfMaxPages: 100,
      }),
    }),
  );
  await page.route("**/api/learn/studio/projects", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ projects: [] }),
      });
    }
    return route.continue();
  });

  let multipartBody = "";
  await page.route("**/api/learn/studio/projects/pdf", async (route) => {
    multipartBody = route.request().postDataBuffer()?.toString("utf8") ?? "";
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        id: PROJECT_ID,
        topic: "Dividend policy",
        language: "en",
        level: "beginner",
        targetMinutes: 4,
        sourceKind: "pdf",
        documentName: "psx-investor-guide.pdf",
        documentPageCount: 1,
        status: "queued",
        stage: "queued",
        bestScore: 0,
        studyPack: null,
        videoReady: false,
        createdAt: "2026-08-06T00:00:00Z",
      }),
    });
  });
  await page.route(`**/api/learn/studio/projects/${PROJECT_ID}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: PROJECT_ID,
        topic: "Dividend policy",
        language: "en",
        level: "beginner",
        targetMinutes: 4,
        sourceKind: "pdf",
        documentName: "psx-investor-guide.pdf",
        documentPageCount: 1,
        status: "generating",
        stage: "extracting_document",
        bestScore: 0,
        studyPack: null,
        videoReady: false,
        createdAt: "2026-08-06T00:00:00Z",
      }),
    }),
  );

  await page.goto("/learn");
  await authSettled(page);
  await page.getByRole("button", { name: "Upload a PDF" }).click();
  await page.getByLabel("Select a private PDF").setInputFiles({
    name: "psx-investor-guide.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 deterministic e2e fixture %%EOF"),
  });
  await page.getByLabel("Lesson focus (optional)").fill("Dividend policy");

  await expect(page.getByTestId("studio-create-card")).toHaveScreenshot(
    "pdf-upload-card.png",
    {
      animations: "disabled",
      maxDiffPixelRatio: 0.01,
    },
  );
  await page.getByRole("button", { name: "Create from PDF" }).click();

  await expect(page).toHaveURL(new RegExp(`/learn/generated/${PROJECT_ID}$`));
  await expect(page.getByRole("status")).toContainText(
    "Reading and checking your private PDF",
  );
  expect(multipartBody).toContain('filename="psx-investor-guide.pdf"');
  expect(multipartBody).toContain("Dividend policy");
});
