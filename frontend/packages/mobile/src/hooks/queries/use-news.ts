// PSX news feed — public GET /api/news (per-symbol) and /api/news/latest.
import { useQuery } from "@tanstack/react-query";

import { publicGet } from "@/lib/api";

export interface NewsItem {
  id: string | number;
  headline: string;
  url: string | null;
  source: string | null;
  published_at: string | null;
  tickers: string[] | null;
  refreshed_at?: string | null;
}

export function useLatestNews(limit: number = 20, enabled: boolean = true) {
  return useQuery<NewsItem[]>({
    queryKey: ["news", "latest", limit],
    queryFn: () => publicGet<NewsItem[]>(`/api/news/latest?limit=${limit}`),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useNews(symbol: string | undefined, limit: number = 20) {
  return useQuery<NewsItem[]>({
    queryKey: ["news", "symbol", symbol, limit],
    queryFn: () => publicGet<NewsItem[]>(`/api/news?symbol=${symbol}&limit=${limit}`),
    enabled: !!symbol,
    staleTime: 5 * 60_000,
  });
}
