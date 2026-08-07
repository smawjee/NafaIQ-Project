// Global test setup. Loaded by vitest.config.ts `setupFiles`.
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, vi } from "vitest";

import { server } from "./mocks/server";

beforeAll(() => {
  // "bypass" rather than "error": several pre-existing tests replace fetch
  // wholesale with vi.stubGlobal, and a handful of third-party modules probe
  // the network on import. Specs that care assert on the response instead.
  server.listen({ onUnhandledRequest: "bypass" });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
});

afterAll(() => server.close());

// jsdom implements neither of these, and both are touched on first paint by
// the Tailwind/Radix layer (useMediaQuery in use-mobile.tsx) and by recharts /
// framer-motion respectively.
vi.stubGlobal(
  "matchMedia",
  vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
);

// Plain assignment, NOT vi.stubGlobal: this config sets `unstubGlobals: true`,
// which restores every stubbed global in an afterEach — so a stubbed
// ResizeObserver disappears partway through a file and recharts'
// ResponsiveContainer throws "ResizeObserver is not defined" on mount. Nothing
// asserts against it, so there is no reason for it to be a mock at all.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof globalThis.ResizeObserver;

vi.stubGlobal(
  "IntersectionObserver",
  class {
    root = null;
    rootMargin = "";
    thresholds = [];
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  },
);

// jsdom has no layout engine, so every element measures 0x0. Recharts and the
// treemap bail out entirely at zero size, rendering nothing to assert against.
Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
  configurable: true,
  value() {
    return {
      width: 1024,
      height: 768,
      top: 0,
      left: 0,
      bottom: 768,
      right: 1024,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    };
  },
});

globalThis.scrollTo = vi.fn() as unknown as typeof globalThis.scrollTo;
