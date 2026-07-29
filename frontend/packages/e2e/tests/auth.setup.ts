import { expect, test as setup } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { VITE_ENV } from "../playwright.config";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.resolve(HERE, "../playwright/.auth/demo.json");

/**
 * Mint a demo session once per run and save it as storageState.
 *
 * This deliberately does NOT drive the "Try Demo" button. Two reasons:
 *
 *  1. Robustness. The button is one affordance on one page; when it fails, every
 *     authed spec fails with it and the diagnosis is indirect (AuthPage.tsx
 *     catches a failed sign-in and turns it into a toast, so the symptom is
 *     "nothing happened"). Talking to the auth endpoint directly makes a broken
 *     session a one-line error.
 *  2. Separation. Whether the demo BUTTON works is a product behaviour and
 *     belongs in its own spec, not in the fixture every other spec depends on.
 *
 * Supabase-js v2 persists its session in localStorage under
 * `sb-<project-ref>-auth-token` (see src/integrations/supabase/client.ts, which
 * sets `storage: localStorage`), so writing that key is all the app needs.
 */
setup("authenticate as the demo account", async ({ page, request }) => {
  const supabaseUrl = VITE_ENV.VITE_SUPABASE_URL;
  const apiKey =
    VITE_ENV.VITE_SUPABASE_ANON_KEY ?? VITE_ENV.VITE_SUPABASE_PUBLISHABLE_KEY;
  const email = VITE_ENV.VITE_DEMO_EMAIL;
  const password = VITE_ENV.VITE_DEMO_PASSWORD;

  expect(
    supabaseUrl && apiKey && email && password,
    "VITE_SUPABASE_URL, an anon/publishable key, VITE_DEMO_EMAIL and VITE_DEMO_PASSWORD must all be " +
      "available. Locally they come from frontend/packages/web/.env; in CI from repository secrets.",
  ).toBeTruthy();

  /**
   * Live failure replay deliberately uses the real sign-in form. This makes
   * authentication visible in the headed browser without putting credentials
   * in a command, log, report, or generated script. Normal CI remains on the
   * faster request-based path below.
   */
  if (process.env.E2E_VISIBLE_LOGIN === "1") {
    await page.goto("/auth");

    const createAccountHeading = page.getByRole("heading", {
      name: /create your account/i,
    });
    if (await createAccountHeading.isVisible().catch(() => false)) {
      const signInHeading = page.getByRole("heading", {
        name: /welcome back/i,
      });
      const switchToSignIn = page.getByRole("button", { name: /^sign in$/i });

      // The auth route is server-rendered. Visibility alone does not mean its
      // React onClick handler is attached, so wait for React's element props
      // before interacting with the SSR button.
      await page.waitForFunction(
        () => {
          const button = Array.from(document.querySelectorAll("button")).find(
            (candidate) => candidate.textContent?.trim() === "Sign In",
          );
          return (
            button !== undefined &&
            Object.keys(button).some((key) => key.startsWith("__reactProps$"))
          );
        },
        undefined,
        { timeout: 30_000 },
      );
      await switchToSignIn.click();
      await expect(signInHeading).toBeVisible();
    }

    await page.locator("#email").fill(email);
    const passwordInput = page.locator("#password");
    await expect(passwordInput).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
    await passwordInput.fill(password);
    await page.getByRole("button", { name: /^sign in$/i }).click();
    await page.waitForURL((url) => url.pathname !== "/auth", {
      timeout: 30_000,
    });

    fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
    await page.context().storageState({ path: AUTH_FILE });
    return;
  }

  const res = await request.post(
    `${supabaseUrl}/auth/v1/token?grant_type=password`,
    {
      headers: { apikey: apiKey, "Content-Type": "application/json" },
      data: { email, password },
    },
  );

  expect(
    res.ok(),
    `Supabase rejected the demo credentials (${res.status()}): ${await res.text()}`,
  ).toBe(true);

  const session = await res.json();
  expect(
    session.access_token,
    "Supabase returned no access_token",
  ).toBeTruthy();

  // supabase-js expects expires_at (absolute, seconds) — the token endpoint
  // includes it, but derive it if a future version stops doing so.
  if (!session.expires_at && session.expires_in) {
    session.expires_at =
      Math.floor(Date.now() / 1000) + Number(session.expires_in);
  }

  const projectRef = new URL(supabaseUrl).hostname.split(".")[0];
  const origin = new URL(process.env.E2E_BASE_URL ?? "http://127.0.0.1:8080")
    .origin;

  const state = {
    cookies: [],
    origins: [
      {
        origin,
        localStorage: [
          {
            name: `sb-${projectRef}-auth-token`,
            value: JSON.stringify(session),
          },
        ],
      },
    ],
  };

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true });
  fs.writeFileSync(AUTH_FILE, JSON.stringify(state, null, 2));
});
