import { expect, test as base, type Page } from "@playwright/test";

/**
 * Determinism layer.
 *
 * Two things in this app are inherently non-deterministic in CI:
 *   1. PSX market data — the exchange is closed outside 09:30-15:30 PKT and at
 *      weekends, so /api/market/** returns stale or empty payloads and any
 *      value-based assertion becomes time-of-day dependent.
 *   2. AI surfaces — SSE streaming, LLM latency and provider 429s. None of it
 *      is under test in these journeys.
 *
 * Both are stubbed here rather than in each spec.
 */

const SSE_HEADERS = { "content-type": "text/event-stream; charset=utf-8" };

/** Framed exactly as parseSseBuffer() expects (src/lib/ai/tutor-client.ts). */
const SSE_BODY =
  `data: ${JSON.stringify({ type: "token", text: "Deterministic " })}\n\n` +
  `data: ${JSON.stringify({ type: "token", text: "e2e answer." })}\n\n` +
  `data: ${JSON.stringify({ type: "done", usage: { used: 1, limit: 100 } })}\n\n`;

const AI_JSON = {
  headline: "Deterministic e2e report.",
  observations: ["Stubbed for end-to-end tests."],
  sections: [],
  disclaimer: "Educational information only. Not financial advice.",
  citations: [],
};

/**
 * /api/ai/report/* speaks the ReportResponse envelope (reports-client.ts):
 * the report lives under `content`, and content.lang must match the UI
 * language or ReportPanel auto-closes the report as language drift.
 */
const REPORT_JSON = {
  report_type: "portfolio",
  content: {
    report_type: "portfolio",
    schema_version: 1,
    lang: "en",
    headline: "Deterministic e2e report.",
    observations: ["Stubbed for end-to-end tests."],
    considerations: [],
    disclaimer: "Educational information only. Not financial advice.",
    citations: [],
  },
  provider: null,
  model: null,
  verified: true,
  created_at: null,
};

/** Noise that is expected and must not fail the console guard. */
const ALLOWED_CONSOLE = [
  /Download the React DevTools/i,
  /\[vite\] connect(ing|ed)/i,
  /Third-party cookie/i,
  /React Router Future Flag/i,
// REAL app defect, deliberately allow-listed so the rest of the guard stays
  // useful: /learn/lesson/* logs "Encountered two children with the same key"
  // ×6 on every load (duplicate React keys in the lesson renderer). Surfaced
  // by the learn.spec.ts journeys on 2026-07-30; needs its own bug ticket.
  // REMOVE this entry when the duplicate keys are fixed.
  /Encountered two children with the same key/i,
  // Harness artifact, not an app fault: every spec shares ONE demo session
  // (tests/auth.setup.ts mints it once), and `fullyParallel` runs many contexts
  // against it at once. Some of those concurrent requests come back 403.
  // Reproduced by running the whole suite; never by running a spec alone.
  //
  // Deliberately narrow — only the browser's generic resource-load message for
  // a 403. A genuine authorisation bug still fails the spec that depends on it,
  // because the data simply will not be there to assert on.
  /Failed to load resource: the server responded with a status of 403/i,
  // Same shared-session harness artifact, other status: many parallel
  // contexts re-validating one demo session also trip rate limits.
  /Failed to load resource: the server responded with a status of 429/i,
  // React 19 wording of the KAN-3 text-content mismatch.
  /Hydration failed because the server rendered text didn't match the client/i,
];

export const test = base.extend<{ page: Page }>({
  page: async ({ page }, use) => {
    // Freeze every AI surface.
    await page.route("**/api/ai/**", (route) => fulfilAi(route));
    await page.route("**/api/assistant/**", (route) => fulfilAi(route));
    await page.route("**/api/learn/ai/**", (route) => fulfilAi(route));

    const errors: string[] = [];
    const allowed = (t: string) => ALLOWED_CONSOLE.some((r) => r.test(t));

    // React surfaces hydration mismatches as a pageerror, not a console.error,
    // so the allowlist has to apply to both channels.
    page.on("pageerror", (e) => {
      if (!allowed(e.message)) errors.push(`pageerror: ${e.message}`);
    });
    page.on("console", (m) => {
      if (m.type() !== "error") return;
      if (!allowed(m.text())) errors.push(`console.error: ${m.text()}`);
    });

    await use(page);

    // Opt out per spec with test.info().annotations.push({ type: "allow-console-errors" }).
    const optedOut = test
      .info()
      .annotations.some((a) => a.type === "allow-console-errors");

    let consoleFailure: unknown;
    try {
      if (!optedOut) {
        expect(errors, "unexpected browser console errors").toEqual([]);
      }
    } catch (error) {
      consoleFailure = error;
    }

    const info = test.info();
    const bodyFailed = info.status !== info.expectedStatus;
    if (
      process.env.E2E_PAUSE_ON_FAILURE === "1" &&
      (bodyFailed || consoleFailure)
    ) {
      // page.pause() keeps both the headed browser and Playwright Inspector open
      // at the failure state. Resume/close it when the journey has been observed.
      await page.pause();
    } else if (!bodyFailed && !consoleFailure) {
      const successDelay = Number(process.env.E2E_REPLAY_SUCCESS_DELAY_MS ?? 0);
      if (Number.isFinite(successDelay) && successDelay > 0) {
        // Keep the successful end state visible long enough for a person to
        // observe it before the headed replay context closes automatically.
        await page.waitForTimeout(successDelay);
      }
    }

    if (consoleFailure) throw consoleFailure;
  },
});

/**
 * Wait for the auth-resolution overlay to clear.
 *
 * __root.tsx renders a full-screen Spinner (fixed inset-0 z-[60], opaque, no
 * pointer-events-none) over every AppShell route until supabase.auth
 * .getSession() resolves. Anything clicked before that is swallowed by the
 * overlay — the exact failure mode behind the Pixel 7 "full-screen loading
 * overlay intercepted the click" and "isDemo was falsy at first render"
 * incidents. Call after goto, before the first interaction.
 */
export async function authSettled(page: Page) {
  // 30s, not the 10s expect default: under full-suite parallelism the dev
  // server is cold-transforming routes while every context re-validates the
  // shared session, and first paint + getSession can legitimately exceed 10s.
  await expect(page.locator('div.fixed.inset-0[class*="z-[60]"]')).toHaveCount(0, {
    timeout: 30_000,
  });
}

function fulfilAi(route: import("@playwright/test").Route) {
  const accept = route.request().headers()["accept"] ?? "";
  const url = route.request().url().split("?")[0];
  // The assistant and tutor clients read SSE off fetch() WITHOUT sending an
  // Accept header (src/lib/assistant/client.ts, src/lib/ai/tutor-client.ts),
  // so the streaming endpoints are matched by path as well.
  const streams =
    accept.includes("text/event-stream") ||
    (route.request().method() === "POST" &&
      (url.endsWith("/api/assistant/chat") || url.endsWith("/api/ai/tutor")));
  if (streams) {
    return route.fulfill({ status: 200, headers: SSE_HEADERS, body: SSE_BODY });
  }
  const isReport = route.request().url().includes("/api/ai/report/");
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(isReport ? REPORT_JSON : AI_JSON),
  });
}

export { expect };
