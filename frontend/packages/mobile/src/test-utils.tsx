// Shared render helper.
//
// Ten-plus test files each hand-rolled the same ThemeProvider / SafeAreaProvider
// / QueryClientProvider wrapper with slightly different SafeArea metrics. This
// is that stack, once.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions, type RenderResult } from "@testing-library/react-native";
import type { ReactElement, ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ThemeProvider } from "@/hooks/use-theme";

/** Non-zero frame + insets: several screens lay out from useSafeAreaInsets and
 *  render nothing measurable at the default 0×0. */
export const SAFE_AREA_METRICS = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

/** Retries off so a failing query surfaces immediately instead of after 3 waits. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  queryClient?: QueryClient;
}

export interface RenderWithProvidersResult extends RenderResult {
  queryClient: QueryClient;
}

export function renderWithProviders(
  ui: ReactElement,
  { queryClient, ...options }: RenderWithProvidersOptions = {},
): RenderWithProvidersResult {
  const client = queryClient ?? makeTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <SafeAreaProvider initialMetrics={SAFE_AREA_METRICS}>
        <QueryClientProvider client={client}>
          <ThemeProvider>{children}</ThemeProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    );
  }

  return { ...render(ui, { wrapper: Wrapper, ...options }), queryClient: client };
}

/** Provider-only wrapper for renderHook. */
export function makeHookWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? makeTestQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { Wrapper, queryClient: client };
}

/**
 * CLAUDE.md §2 requires every interactive element to be ≥ 44×44 pt. RN's test
 * renderer has no layout engine, so this reads the declared style instead —
 * which is what the rule is actually about.
 */
export function touchTargetSize(element: {
  props: { style?: unknown; hitSlop?: unknown };
}): { width: number; height: number } {
  const flat = flattenStyle(element.props.style);
  const slop = element.props.hitSlop as
    | { top?: number; bottom?: number; left?: number; right?: number }
    | number
    | undefined;

  const slopX = typeof slop === "number" ? slop * 2 : (slop?.left ?? 0) + (slop?.right ?? 0);
  const slopY = typeof slop === "number" ? slop * 2 : (slop?.top ?? 0) + (slop?.bottom ?? 0);

  const width = num(flat.width) || num(flat.minWidth) || num(flat.paddingHorizontal) * 2;
  const height = num(flat.height) || num(flat.minHeight) || num(flat.paddingVertical) * 2;

  return { width: width + slopX, height: height + slopY };
}

function num(v: unknown): number {
  return typeof v === "number" ? v : 0;
}

function flattenStyle(style: unknown): Record<string, unknown> {
  if (!style) return {};
  if (Array.isArray(style)) return Object.assign({}, ...style.map(flattenStyle));
  return style as Record<string, unknown>;
}

export * from "@testing-library/react-native";
