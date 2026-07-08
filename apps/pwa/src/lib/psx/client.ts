import type {
  ApiMarketSnapshotItem,
  ApiOHLCVBar,
  ApiSymbolInfo,
  ApiCompanyProfile,
  ApiFundamentalsData,
  ApiAnnouncementItem,
  ApiDividendEvent,
  ApiIndexBar,
  ApiSectorDataItem,
  ApiIndicatorPayload,
  ApiSignal,
  BatchSignalsResponse,
  ScreenerRequest,
  ScreenerResponse,
  BacktestRequest,
  ApiBacktestResult,
} from "./types";

const BASE = import.meta.env.VITE_PSX_API_URL || "http://localhost:8000";
const TOKEN = import.meta.env.VITE_PSX_API_TOKEN || "";

async function get<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

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

export function fetchProfile(symbol: string): Promise<ApiCompanyProfile> {
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

export function fetchSectors(): Promise<ApiSectorDataItem[]> {
  return get<ApiSectorDataItem[]>("/api/sectors");
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

export function fetchSignal(symbol: string): Promise<ApiSignal> {
  return get<ApiSignal>(`/api/signal/${symbol}`);
}

export function fetchBatchSignals(limit = 50): Promise<BatchSignalsResponse> {
  return post<BatchSignalsResponse>("/api/signals/batch", { limit });
}
