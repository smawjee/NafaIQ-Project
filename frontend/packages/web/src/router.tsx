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
    defaultPreload: "viewport",
    defaultPreloadStaleTime: 0,
  });

  return router;
};
