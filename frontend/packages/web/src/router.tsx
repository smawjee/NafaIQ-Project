import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Library defaults were retry:3 + refetchOnWindowFocus:true, so a slow
        // endpoint was retried 3× (with backoff) before the UI gave up, and
        // every tab refocus re-hit the backend for dozens of queries. retry:1
        // fails fast; live figures still refresh via each hook's own
        // refetchInterval, so nothing goes stale. Per-hook staleTime overrides
        // are left untouched.
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    // "intent" (hover/focus), NOT "viewport" (KAN-4). Viewport preloading fired
    // for every link the moment it scrolled into view, so dozens of speculative
    // preloads ran concurrently; navigating away evicted their matches while
    // still in flight, and router-core's loadRouteMatch dereferences an evicted
    // match unguarded — "Cannot read properties of undefined (reading
    // '_nonReactive')", ~12 console errors per landing-page visit. The library
    // bug persists upstream (unguarded getMatch derefs are still in
    // router-core 1.171.15); intent preloading avoids triggering it by only
    // preloading the one link the user is about to click.
    defaultPreload: "intent",
    defaultPreloadStaleTime: 0,
  });

  return router;
};
