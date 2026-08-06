// FastAPI backend client. Ported from the web app's src/lib/api.ts +
// src/lib/psx/client.ts — keep endpoint paths and auth modes in sync with it.
//
// Two auth tiers, matching backend/src/app/middleware/auth.py:
//   - Public market/reference routes: optional shared PSX token.
//   - User-owned routes (portfolio, finance, alerts, profile, watchlist):
//     the Supabase session JWT, validated server-side by require_user.
import Constants from "expo-constants";

import type {
  ApiMarketSnapshotItem,
  ApiOHLCVBar,
  ApiSymbolInfo,
  ApiCompanyProfile,
  ApiFundamentalsData,
  ApiAnnouncementItem,
  ApiDividendEvent,
  ApiIndexBar,
  ApiIndexCard,
  ApiScreenerMetric,
  ApiSectorDataItem,
  ApiHeatmapResponse,
  ApiIndicatorPayload,
  ApiSignal,
  ApiTrackRecord,
  BatchSignalsResponse,
  ScreenerRequest,
  ScreenerResponse,
  BacktestRequest,
  ApiBacktestResult,
} from "@nafaiq/shared";

import { supabase } from "./supabase";
import type { ApiSignalDetail } from "./signals";
import { toLegacySignal } from "./signals";

const EXPLICIT_URL = process.env.EXPO_PUBLIC_API_URL;
const PSX_TOKEN = process.env.EXPO_PUBLIC_PSX_API_TOKEN || "";

/**
 * In dev, fall back to the machine running Metro (works on physical devices
 * and emulators alike — Constants.expoConfig.hostUri is e.g. "192.168.1.5:8081").
 * Production builds MUST set EXPO_PUBLIC_API_URL.
 */
function resolveBaseUrl(): string {
  if (EXPLICIT_URL) return EXPLICIT_URL.replace(/\/$/, "");
  const host = Constants.expoConfig?.hostUri?.split(":")[0];
  if (host) return `http://${host}:8000`;
  if (!__DEV__) {
    throw new Error("[api] EXPO_PUBLIC_API_URL must be set in production builds");
  }
  return "http://localhost:8000";
}

export const API_BASE_URL = resolveBaseUrl();

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request<T>(
  path: string,
  init: RequestInit & { headers?: Record<string, string> } = {},
): Promise<T> {
  const res = await fetch(apiUrl(path), init);
  const payload = await res.text();
  if (!res.ok) {
    let detail = payload;
    try {
      const parsed = JSON.parse(payload) as { detail?: string };
      detail = parsed.detail ?? payload;
    } catch {
      // Preserve the plain response body when the server did not return JSON.
    }
    throw new Error(detail || `${path}: ${res.status} ${res.statusText}`);
  }
  if (!payload) return undefined as T;
  return JSON.parse(payload) as T;
}

// === Public requests (optional shared PSX token) ===

function publicHeaders(json = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (PSX_TOKEN) headers["Authorization"] = `Bearer ${PSX_TOKEN}`;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function get<T>(path: string): Promise<T> {
  return request<T>(path, { headers: publicHeaders() });
}

async function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: publicHeaders(true),
    body: JSON.stringify(body),
  });
}

// Generic public GET for endpoints without a dedicated fetcher above
// (news, funds, macro, dividends, …). Uses the optional shared PSX token.
export function publicGet<T>(path: string): Promise<T> {
  return get<T>(path);
}

/**
 * POST to an endpoint that takes no credential at all (backend PUBLIC_PATHS,
 * e.g. password recovery and client telemetry). Distinct from userPost, which
 * attaches the session JWT — these callers can run for signed-out users.
 */
export function publicPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// === User-authenticated requests (Supabase session JWT) ===

async function userHeaders(json = false): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error("Not authenticated");
  const headers: Record<string, string> = {
    Authorization: `Bearer ${data.session.access_token}`,
  };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export async function userGet<T>(path: string): Promise<T> {
  return request<T>(path, { headers: await userHeaders() });
}

export async function userPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: await userHeaders(true),
    body: JSON.stringify(body),
  });
}

export async function userPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: await userHeaders(true),
    body: JSON.stringify(body),
  });
}

/** Authenticated multipart upload. The runtime supplies the boundary header. */
export async function userUpload<T>(path: string, body: FormData): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: await userHeaders(),
    body,
  });
}

export async function userDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE", headers: await userHeaders() });
}

// === Public market/reference endpoints ===

export function fetchMarketSnapshot(): Promise<ApiMarketSnapshotItem[]> {
  return get<ApiMarketSnapshotItem[]>("/api/market/snapshot");
}

export function fetchQuote(symbol: string): Promise<ApiMarketSnapshotItem> {
  return get<ApiMarketSnapshotItem>(`/api/quote/${symbol}`);
}

export function fetchHistory(symbol: string, days?: number): Promise<ApiOHLCVBar[]> {
  const qs = days ? `?days=${days}` : "";
  return get<ApiOHLCVBar[]>(`/api/quote/${symbol}/history${qs}`);
}

export function fetchSymbols(): Promise<ApiSymbolInfo[]> {
  return get<ApiSymbolInfo[]>("/api/symbols");
}

export function fetchFundamentals(symbol: string): Promise<ApiFundamentalsData> {
  return get<ApiFundamentalsData>(`/api/fundamentals/${symbol}`);
}

export function fetchCompanyProfile(symbol: string): Promise<ApiCompanyProfile> {
  return get<ApiCompanyProfile>(`/api/profile/${symbol}`);
}

export function fetchAnnouncements(
  symbol?: string,
  limit?: number,
): Promise<ApiAnnouncementItem[]> {
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (limit) params.set("limit", String(limit));
  const qs = params.toString();
  return get<ApiAnnouncementItem[]>(`/api/announcements${qs ? `?${qs}` : ""}`);
}

export function fetchDividends(symbol: string): Promise<ApiDividendEvent[]> {
  return get<ApiDividendEvent[]>(`/api/dividends/${symbol}`);
}

export function fetchIndexData(code: string): Promise<ApiIndexBar[]> {
  return get<ApiIndexBar[]>(`/api/index/${code}`);
}

export function fetchIndexCards(): Promise<ApiIndexCard[]> {
  return get<ApiIndexCard[]>("/api/index/cards");
}

export function fetchScreenerMetrics(): Promise<ApiScreenerMetric[]> {
  return get<ApiScreenerMetric[]>("/api/market/metrics");
}

export function fetchSectors(): Promise<ApiSectorDataItem[]> {
  return get<ApiSectorDataItem[]>("/api/sectors");
}

export function fetchHeatmap(): Promise<ApiHeatmapResponse> {
  return get<ApiHeatmapResponse>("/api/market/heatmap");
}

export function fetchIndicators(
  symbol: string,
  indicators?: string[],
): Promise<ApiIndicatorPayload> {
  const body = indicators ? { indicators } : {};
  return post<ApiIndicatorPayload>(`/api/indicators/${symbol}`, body);
}

export function runScreener(params: ScreenerRequest): Promise<ScreenerResponse> {
  return post<ScreenerResponse>("/api/screener", params);
}

export function runBacktest(params: BacktestRequest): Promise<ApiBacktestResult> {
  return post<ApiBacktestResult>("/api/backtest", params);
}

/** Compact row shape for list surfaces (screener, watchlist). */
export function fetchSignal(symbol: string): Promise<ApiSignal> {
  return get<ApiSignalDetail>(`/api/signals/${symbol}`).then(toLegacySignal);
}

export function fetchBatchSignals(limit = 50): Promise<BatchSignalsResponse> {
  return post<{ signals: ApiSignalDetail[]; count: number }>("/api/signals/batch", { limit }).then((response) => ({ signals: response.signals.map(toLegacySignal), count: response.count }));
}

/** Full engine response — technical setup, measurement quality and context. */
export function fetchSignalDetail(symbol: string): Promise<ApiSignalDetail> {
  return get<ApiSignalDetail>(`/api/signals/${symbol}`);
}

export function fetchSignalTrackRecord(): Promise<ApiTrackRecord> {
  return get<ApiTrackRecord>("/api/signals/track-record");
}
