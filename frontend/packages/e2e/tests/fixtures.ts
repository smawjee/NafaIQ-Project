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

/** Noise that is expected and must not fail the console guard. */
const ALLOWED_CONSOLE = [
  /Download the React DevTools/i,
  /\[vite\] connect(ing|ed)/i,
  /Third-party cookie/i,
  /React Router Future Flag/i,
  
  // Harness artifact, not an app fault: every spec shares ONE demo session
  // (tests/auth.setup.ts mints it once), and `fullyParallel` runs many contexts
  // against it at once. Some of those concurrent requests come back 403.
  // Reproduced by running the whole suite; never by running a spec alone.
  //
  // Deliberately narrow — only the browser's generic resource-load message for
  // a 403. A genuine authorisation bug still fails the spec that depends on it,
  // because the data simply will not be there to assert on.
  /Failed to load resource: the server responded with a status of 403/i,
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
    if (!optedOut) {
      expect(errors, "unexpected browser console errors").toEqual([]);
    }
  },
});

function fulfilAi(route: import("@playwright/test").Route) {
  const accept = route.request().headers()["accept"] ?? "";
  if (accept.includes("text/event-stream")) {
    return route.fulfill({ status: 200, headers: SSE_HEADERS, body: SSE_BODY });
  }
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(AI_JSON),
  });
}

export { expect };
