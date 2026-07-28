// Shared render helper.
//
// Before this existed, each test file hand-rolled its own mocking (see the
// duplicated mockSessionToken/sseResponse helpers in lib/ai/reports-client.test.ts
// and lib/assistant/client.test.ts). Component tests need the same provider
// stack the app mounts in src/routes/__root.tsx, so it lives here once.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import { configureStore, type Reducer } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import type { ReactElement, ReactNode } from "react";

import { rootReducer } from "@/store";

/** Retries off: a failing query should surface immediately, not after 3 waits. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}

export interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  /** Seed redux state, e.g. a populated watchlist or demo-user session. */
  preloadedState?: Record<string, unknown>;
  queryClient?: QueryClient;
}

export interface RenderWithProvidersResult extends RenderResult {
  queryClient: QueryClient;
  store: ReturnType<typeof configureStore>;
}

export function renderWithProviders(
  ui: ReactElement,
  { preloadedState, queryClient, ...options }: RenderWithProvidersOptions = {},
): RenderWithProvidersResult {
  const client = queryClient ?? makeTestQueryClient();
  const store = configureStore({
    reducer: rootReducer as Reducer,
    preloadedState,
    // The persistence middleware writes to localStorage on every action; tests
    // assert on state, not on the side effect.
    middleware: (getDefault) => getDefault({ serializableCheck: false }),
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <Provider store={store}>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </Provider>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...options }),
    queryClient: client,
    store,
  };
}

/** Provider-only wrapper for renderHook. */
export function makeHookWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? makeTestQueryClient();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { Wrapper, queryClient: client };
}

// Re-exported so a test file needs one import, not three. This module is never
// bundled into the app, so the Fast Refresh constraint does not apply.
// eslint-disable-next-line react-refresh/only-export-components
export * from "@testing-library/react";
export { default as userEvent } from "@testing-library/user-event";
