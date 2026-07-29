/// <reference types="vitest" />
// Dedicated Vitest config.
//
// Before this file existed, `vitest run` fell through to vite.config.ts and
// therefore loaded the whole @lovable.dev/vite-tanstack-config plugin chain
// (TanStack Start + nitro + componentTagger) just to run unit tests. That
// worked, but it pinned the test environment to `node` — which is why the suite
// had no component tests at all. Keeping tests on their own config gives us a
// jsdom environment and keeps the SSR/nitro machinery out of the test run.
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const src = fileURLToPath(new URL("./src", import.meta.url));
const shared = fileURLToPath(new URL("../shared/src", import.meta.url));

export default defineConfig({
  // The React plugin is deliberately not used: tests need JSX transformed, not
  // Fast Refresh. Vite 7 / Vitest 4 transform with oxc, whose automatic JSX
  // runtime is the default — no extra configuration required.
  resolve: {
    alias: {
      // Mirrors tsconfig.json "paths". vite-tsconfig-paths is injected by the
      // lovable preset, which this config intentionally does not load.
      "@": src,
      "@nafaiq/shared": shared,
    },
  },

  test: {
    environment: "jsdom",
    setupFiles: ["./src/setup-tests.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Tests import { describe, it, expect } from "vitest" explicitly — matching
    // the convention already used by the 9 pre-existing test files.
    globals: false,
    restoreMocks: true,
    unstubGlobals: true,
    css: false,
  },
});
