// Single shared React Query client (mirrors the web app's router.tsx setup).
// Data is currently static/seeded; React Query is wired for future live data.
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
