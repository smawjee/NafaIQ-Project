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
  ApiHeatmapResponse,
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

// === User-authenticated requests (use Supabase session JWT) ===
async function getSupabaseSession() {
  const { supabase } = await import("@/integrations/supabase/client");
  const { data } = await supabase.auth.getSession();
  return data.session;
}

async function userGet<T>(path: string): Promise<T> {
  const session = await getSupabaseSession();
  if (!session) throw new Error("Not authenticated");
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  };
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function userPost<T>(path: string, body: unknown): Promise<T> {
  const session = await getSupabaseSession();
  if (!session) throw new Error("Not authenticated");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
  };
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function userPatch<T>(path: string, body: unknown): Promise<T> {
  const session = await getSupabaseSession();
  if (!session) throw new Error("Not authenticated");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
  };
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function userDelete<T>(path: string): Promise<T> {
  const session = await getSupabaseSession();
  if (!session) throw new Error("Not authenticated");
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  };
  const res = await fetch(`${BASE}${path}`, { method: "DELETE", headers });
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

export function fetchSignal(symbol: string): Promise<ApiSignal> {
  return get<ApiSignal>(`/api/signal/${symbol}`);
}

export function fetchBatchSignals(limit = 50): Promise<BatchSignalsResponse> {
  return post<BatchSignalsResponse>("/api/signals/batch", { limit });
}

// === User-authenticated request exports ===
export { userGet, userPost, userPatch, userDelete };

// === Allocation / performance / stock transactions (user-scoped) ===

export interface PortfolioAllocationItem {
  symbol?: string;
  sector?: string;
  value: number;
  pct: number;
}

export interface PortfolioAllocation {
  by: "stock" | "sector";
  items: PortfolioAllocationItem[];
}

export interface PortfolioPerformancePoint {
  date: string;
  label: string;
  value: number;
  benchmark: number;
}

export interface PortfolioPerformance {
  days: number;
  points: PortfolioPerformancePoint[];
}

export function fetchPortfolioAllocation(by: "stock" | "sector"): Promise<PortfolioAllocation> {
  return userGet<PortfolioAllocation>(`/api/portfolio/allocation?by=${by}`);
}

export function fetchPortfolioPerformance(days: number = 180): Promise<PortfolioPerformance> {
  return userGet<PortfolioPerformance>(`/api/portfolio/performance?days=${days}`);
}

// === Zakat (user-scoped) ===

export interface ZakatSettings {
  user_id: string;
  method: string;
  custom_rate_pct: number | null;
  nisab_source: string;
  nisab_value_pkr: number | null;
  include_cash: boolean;
  include_investments: boolean;
  include_receivables: boolean;
  notes: string | null;
  updated_at: string | null;
}

export interface ZakatRecord {
  id: number;
  user_id: string;
  islamic_year: string;
  method: string;
  nisab_value_pkr: number;
  total_assets_pkr: number;
  total_deductions_pkr: number;
  net_zakatable_pkr: number;
  rate_pct: number;
  zakat_due_pkr: number;
  breakdown: Record<string, unknown>;
  calculated_at: string;
  created_at: string;
}

export function fetchZakatSettings(): Promise<ZakatSettings> {
  return userGet<ZakatSettings>("/api/finance/zakat/settings");
}

export function updateZakatSettings(updates: Partial<ZakatSettings>): Promise<ZakatSettings> {
  return userPatch<ZakatSettings>("/api/finance/zakat/settings", updates);
}

export function fetchZakatHistory(limit: number = 20): Promise<ZakatRecord[]> {
  return userGet<ZakatRecord[]>(`/api/finance/zakat/history?limit=${limit}`);
}

export function calculateZakat(body: {
  islamic_year: string;
  total_assets_pkr: number;
  total_deductions_pkr?: number;
  nisab_value_pkr: number;
  rate_pct?: number;
  method?: string;
  breakdown?: Record<string, unknown>;
  save?: boolean;
}): Promise<unknown> {
  return userPost<unknown>("/api/finance/zakat/calculate", body);
}

// === Alerts (user-scoped) ===

export interface AlertEvent {
  id: number;
  user_id: string;
  alert_id: number | null;
  alert_type: "stock_price" | "bill" | "budget" | "goal" | "system";
  symbol: string | null;
  title: string;
  body: string;
  payload: Record<string, unknown>;
  channel: "in_app" | "email" | "push";
  delivered_at: string | null;
  read_at: string | null;
  created_at: string;
}

export interface AppAlert {
  id: number;
  user_id: string;
  type: "stock_price" | "bill" | "budget" | "goal";
  title: string;
  meta: Record<string, unknown>;
  enabled: boolean;
  triggered_at: string | null;
  created_at: string;
}

export function fetchAlertEvents(limit: number = 50): Promise<AlertEvent[]> {
  return userGet<AlertEvent[]>(`/api/alerts/events?limit=${limit}`);
}

export function markAlertEventRead(id: number): Promise<{ id: number; read_at_set: boolean }> {
  return userPatch<{ id: number; read_at_set: boolean }>(`/api/alerts/events/${id}/read`, {});
}

export function fetchAllAlerts(): Promise<AppAlert[]> {
  return userGet<AppAlert[]>("/api/alerts");
}

export function createAlert(data: { type: AppAlert["type"]; title: string; meta?: Record<string, unknown>; enabled?: boolean }): Promise<AppAlert> {
  return userPost<AppAlert>("/api/alerts", data);
}

export function toggleAlert(id: number, enabled: boolean): Promise<{ id: number; enabled: boolean }> {
  return userPatch<{ id: number; enabled: boolean }>(`/api/alerts/${id}`, { enabled });
}

export function deleteAlert(id: number): Promise<{ deleted: number }> {
  return userDelete<{ deleted: number }>(`/api/alerts/${id}`);
}

export function evaluateAlerts(): Promise<{ price_alerts: number; bill_reminders: number; budget_alerts: number; goal_alerts: number }> {
  return userPost<{ price_alerts: number; bill_reminders: number; budget_alerts: number; goal_alerts: number }>("/api/alerts/evaluate", {});
}
