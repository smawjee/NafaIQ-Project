import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "../../..");
const BACKEND_DIR = path.join(REPO_ROOT, "backend");

const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 8080);
const API_PORT = Number(process.env.E2E_API_PORT ?? 8000);

const BASE_URL = process.env.E2E_BASE_URL ?? `http://127.0.0.1:${WEB_PORT}`;

/** Point at a deployed backend (Railway) to skip the local uvicorn entirely. */
const EXTERNAL_API = process.env.E2E_API_URL?.trim() || "";
const API_URL = EXTERNAL_API || `http://127.0.0.1:${API_PORT}`;

/** venv python locally; plain `python` on CI, where setup-python owns PATH. */
const PYTHON =
  process.env.E2E_PYTHON ??
  (process.env.CI ? "python" : path.join(BACKEND_DIR, ".venv/bin/python"));

/**
 * Environment handed to the Vite dev server.
 *
 * The web package's .env is read HERE rather than relying on the caller to
 * source it, and rather than relying on Vite to pick it up. Neither assumption
 * held: run from this package, the dev server started without
 * VITE_DEMO_PASSWORD, so use-demo.ts threw "Demo password not configured" —
 * which AuthPage.tsx catches and turns into a toast. The result was a demo
 * sign-in that failed with no network request, no page error and no obvious
 * cause.
 *
 * Precedence: real process env > web/.env file > nothing. Only the API base URL
 * is forced, because that is the one value the e2e run must control so the app
 * under test talks to OUR backend.
 */
function readWebEnvFile(): Record<string, string> {
  const file = path.join(REPO_ROOT, "frontend/packages/web/.env");
  if (!fs.existsSync(file)) return {};
  const out: Record<string, string> = {};
  for (const raw of fs.readFileSync(file, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim().replace(/^["']|["']$/g, "");
    if (key.startsWith("VITE_") && value) out[key] = value;
  }
  return out;
}

export const VITE_ENV: Record<string, string> = {
  ...readWebEnvFile(),
  // process.env wins, so CI secrets override whatever a developer has locally.
  ...Object.fromEntries(
    Object.entries(process.env).filter(([k, v]) => k.startsWith("VITE_") && v),
  ) as Record<string, string>,
  VITE_API_URL: API_URL,
  VITE_PSX_API_URL: API_URL,
};

export const AUTH_STATE = path.join(HERE, "playwright/.auth/demo.json");

export default defineConfig({
  testDir: "./tests",
  // Kept OUT of reports/ so the html reporter's folder wipe cannot race the
  // json file the qa-e2e-triage skill reads.
  outputDir: "./test-results",

  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // 2 on CI so a genuinely transient failure lands as `flaky` rather than
  // `unexpected` — that distinction is what stops the triage skill filing a
  // Jira bug for a blip.
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : "50%",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  globalTimeout: 25 * 60 * 1000,

  reporter: [
    ["list"],
    ["html", { outputFolder: "reports/html", open: "never" }],
    // STABLE PATH — consumed by .claude/skills/qa-e2e-triage.
    ["json", { outputFile: "reports/results.json" }],
    ...(process.env.CI ? [["github"] as const] : []),
  ],

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // PageTransition in src/routes/__root.tsx short-circuits when
    // useReducedMotion() is true, so AnimatePresence never runs. Removes the
    // "element detached mid-animation" class of flake outright.
    // Lives under contextOptions — it is a browser-context option, not a
    // top-level `use` key.
    contextOptions: { reducedMotion: "reduce" },
    colorScheme: "dark",
    locale: "en-PK",
    timezoneId: "Asia/Karachi",
    viewport: { width: 1440, height: 900 },
  },

  projects: [
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "public-chromium",
      testMatch: /public\/.*\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], storageState: { cookies: [], origins: [] } },
    },
    {
      name: "authed-chromium",
      testMatch: /authed\/.*\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"], storageState: AUTH_STATE },
    },
    {
      // Nightly only — see .github/workflows/nightly-e2e.yml.
      name: "authed-mobile",
      testMatch: /authed\/.*\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Pixel 7"], storageState: AUTH_STATE },
    },
  ],

  webServer: [
    // 1) FastAPI. Skipped when E2E_API_URL points at a deployed backend.
    ...(EXTERNAL_API
      ? []
      : [
          {
            command: `${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
            cwd: BACKEND_DIR,
            // pytest gets pythonpath from pyproject; uvicorn does not read it.
            env: { PYTHONPATH: "src", LANGFUSE_TRACING_ENABLED: "false" },
            url: `${API_URL}/api/health`,
            timeout: 120_000,
            reuseExistingServer: !process.env.CI,
            stdout: "pipe" as const,
            stderr: "pipe" as const,
          },
        ]),
    // 2) Web. `vite dev`, NOT `vite preview`: @lovable.dev/vite-tanstack-config
    // defaults nitro to preset "cloudflare-module", so the production build has
    // no Node server to preview.
    {
      command: `pnpm --filter @nafaiq/web exec vite dev --host 127.0.0.1 --port ${WEB_PORT}`,
      cwd: REPO_ROOT,
      url: BASE_URL,
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
      env: VITE_ENV,
      stdout: "pipe" as const,
      stderr: "pipe" as const,
    },
  ],
});
