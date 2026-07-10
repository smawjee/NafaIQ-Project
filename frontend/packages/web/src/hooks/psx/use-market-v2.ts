import { API_BASE_URL } from "@/lib/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

export interface LatestPrice {
  symbol: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number;
  day_high: number | null;
  day_low: number | null;
  refreshed_at: string | null;
  previous_close: number | null;
  source?: string;
}

async function publicGet<T>(path: string): Promise<T> {
  // Read from PUBLIC PSX API. Reads use the PSX token if available.
  // We deliberately do NOT pass a user token here because these endpoints
  // are public and any user (or anonymous) can call them.
  const base = API_BASE_URL;
  const token = (import.meta as { env?: Record<string, string> }).env?.VITE_PSX_API_TOKEN || "";
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${base}${path}`, { headers });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return (await res.json()) as T;
}

export function useLatestPrice(symbol: string, enabled: boolean = true) {
  return useQuery<LatestPrice>({
    queryKey: ["psx", "latest", symbol],
    queryFn: () => publicGet<LatestPrice>(`/api/market/latest/${encodeURIComponent(symbol)}`),
    enabled: enabled && !!symbol,
    staleTime: 8_000,
    placeholderData: keepPreviousData,
  });
}

export function useSectorMap(enabled: boolean = true) {
  return useQuery<Record<string, string | null>>({
    queryKey: ["psx", "sector-map"],
    queryFn: () => publicGet<Record<string, string | null>>("/api/market/sector-map"),
    enabled,
    staleTime: 60 * 60_000,
  });
}

export function useKse100(days: number = 365, enabled: boolean = true) {
  return useQuery<{
    latest: { value: number; date: string; change: number; change_pct: number } | null;
    series: {
      date: string;
      open: number;
      high: number;
      low: number;
      close: number;
      volume: number;
    }[];
  }>({
    queryKey: ["psx", "kse100", days],
    queryFn: () =>
      publicGet<{
        latest: { value: number; date: string; change: number; change_pct: number } | null;
        series: {
          date: string;
          open: number;
          high: number;
          low: number;
          close: number;
          volume: number;
        }[];
      }>(`/api/market/kse100?days=${days}`),
    enabled,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}
