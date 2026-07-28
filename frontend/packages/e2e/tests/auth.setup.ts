import { expect, test as setup } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.resolve(HERE, "../playwright/.auth/demo.json");

/**
 * Sign in once per run and save the session for the authed project.
 *
 * Per-test login would cost a real Supabase round-trip per spec and give
 * Supabase rate-limiting a chance to fail an unrelated assertion. As a setup
 * project this is ONE test that fails loudly and blocks its dependents.
 */
setup("authenticate as the demo account", async ({ page, context }) => {
  expect(
    process.env.VITE_DEMO_PASSWORD,
    'VITE_DEMO_PASSWORD must be set — src/hooks/use-demo.ts throws "Demo password not configured" when blank',
  ).toBeTruthy();

  await page.goto("/auth");

  // The same "Try Demo" affordance exists on the landing nav; /auth is the
  // single-button surface. .first() guards against the mobile drawer copy.
  const tryDemo = page.getByRole("button", { name: /try demo/i }).first();
  if (!(await tryDemo.isVisible().catch(() => false))) {
    // Fallback: the landing page nav (src/features/landing/components/Nav.tsx).
    await page.goto("/");
  }
  await page.getByRole("button", { name: /try demo/i }).first().click();

  // useDemo().signInAsDemo() navigates to /app on success.
  await page.waitForURL("**/app", { timeout: 30_000 });
  await expect(page).toHaveTitle(/Dashboard — NafaIQ/);

  const state = await context.storageState();

  // Keep ONLY the Supabase session (sb-<ref>-auth-token). Dropping
  // "nafaiq:redux:v1" (src/store/middleware.ts) means every spec starts from a
  // freshly seeded demo store, so a mutation spec cannot leak into the next.
  for (const origin of state.origins) {
    origin.localStorage = origin.localStorage.filter((e) => e.name.startsWith("sb-"));
  }

  expect(
    state.origins.flatMap((o) => o.localStorage).length,
    "no Supabase session token was persisted — did the demo sign-in actually succeed?",
  ).toBeGreaterThan(0);

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
  fs.writeFileSync(AUTH_FILE, JSON.stringify(state, null, 2));
});
