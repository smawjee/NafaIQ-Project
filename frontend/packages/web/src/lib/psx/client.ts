import { API_BASE_URL } from "@/lib/api";

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
  ApiTreemap,
  ApiIndicatorPayload,
  ApiSignal,
  BatchSignalsResponse,
  ScreenerRequest,
  ScreenerResponse,
  BacktestRequest,
  ApiBacktestResult,
  ApiMutualFund,
  ApiFundNavHistory,
} from "./types";

// Re-export mutual fund types for use in hooks
export type { ApiMutualFund, ApiFundNavHistory, ApiDividendEvent };

const BASE = API_BASE_URL;
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
  return get<ApiDividendEvent[]>(`/api/dividends/${encodeURIComponent(symbol)}`);
}

/**
 * All dividend events across every symbol, newest ex_date first. One request —
 * the calendar previously fanned out ~30 per-symbol calls on mount.
 */
export function fetchAllDividends(limit = 100): Promise<ApiDividendEvent[]> {
  return get<ApiDividendEvent[]>(`/api/dividends?limit=${limit}`);
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


export function fetchTreemap(): Promise<ApiTreemap> {
  return get<ApiTreemap>("/api/market/treemap");
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

export function createAlert(data: {
  type: AppAlert["type"];
  title: string;
  meta?: Record<string, unknown>;
  enabled?: boolean;
}): Promise<AppAlert> {
  return userPost<AppAlert>("/api/alerts", data);
}

export function toggleAlert(
  id: number,
  enabled: boolean,
): Promise<{ id: number; enabled: boolean }> {
  return userPatch<{ id: number; enabled: boolean }>(`/api/alerts/${id}`, { enabled });
}

export function deleteAlert(id: number): Promise<{ deleted: number }> {
  return userDelete<{ deleted: number }>(`/api/alerts/${id}`);
}

export function evaluateAlerts(): Promise<{
  price_alerts: number;
  bill_reminders: number;
  budget_alerts: number;
  goal_alerts: number;
}> {
  return userPost<{
    price_alerts: number;
    bill_reminders: number;
    budget_alerts: number;
    goal_alerts: number;
  }>("/api/alerts/evaluate", {});
}

// === Macro (SBP) ===

export interface ApiMacroRate {
  series: string;
  date: string;
  value: number | null;
  refreshed_at?: string;
}

export interface ApiMacroFx {
  currency: string;
  date: string | null;
  buy: number | null;
  sell: number | null;
}

export function fetchMacroRates(series?: string): Promise<ApiMacroRate[]> {
  const qs = series ? `?series=${encodeURIComponent(series)}` : "";
  return get<ApiMacroRate[]>(`/api/macro/rates${qs}`);
}

export function fetchMacroFx(): Promise<ApiMacroFx[]> {
  return get<ApiMacroFx[]>("/api/macro/fx");
}

export function fetchPolicyRate(): Promise<ApiMacroRate> {
  return get<ApiMacroRate>("/api/macro/policy-rate");
}

// === News (Business Recorder) ===

export interface ApiNewsItem {
  id: number;
  headline: string;
  url: string;
  source: string | null;
  published_at: string | null;
  tickers: string[] | null;
  body: string | null;
  summary: string | null;
  refreshed_at?: string;
}

export function fetchNews(symbol?: string, limit = 20): Promise<ApiNewsItem[]> {
  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  params.set("limit", String(limit));
  return get<ApiNewsItem[]>(`/api/news?${params.toString()}`);
}

export function fetchLatestNews(limit = 10): Promise<ApiNewsItem[]> {
  return get<ApiNewsItem[]>(`/api/news/latest?limit=${limit}`);
}

// === Filings ===

export interface ApiFiling {
  announcement_id: string;
  symbol: string | null;
  type: string | null;
  filed_at: string | null;
  pdf_url: string | null;
  pdf_path?: string | null;
  text_content?: string | null;
  page_count?: number | null;
  refreshed_at?: string;
}

export function fetchFilings(symbol: string, limit = 50): Promise<ApiFiling[]> {
  return get<ApiFiling[]>(`/api/filings/${encodeURIComponent(symbol)}?limit=${limit}`);
}

export function searchFilings(symbol: string, q: string, limit = 20): Promise<ApiFiling[]> {
  return get<ApiFiling[]>(
    `/api/filings/${symbol}/search?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
}

export function fetchFiling(symbol: string, announcementId: string): Promise<ApiFiling> {
  return get<ApiFiling>(`/api/filings/${symbol}/${announcementId}`);
}

// === Mutual Funds (MUFAP) ===

export function fetchMutualFunds(): Promise<ApiMutualFund[]> {
  return get<ApiMutualFund[]>("/api/funds");
}

export function fetchFundNavHistory(fundCode: string, limit = 100): Promise<ApiFundNavHistory[]> {
  return get<ApiFundNavHistory[]>(`/api/funds/${fundCode}/nav?limit=${limit}`);
}

// === Unusual activity ===

export interface ApiUnusualActivity {
  symbol: string;
  ts: string;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
  volume_ratio: number | null;
  reason: string | null;
}

export function fetchUnusualActivity(limit = 20): Promise<ApiUnusualActivity[]> {
  return get<ApiUnusualActivity[]>(`/api/market/unusual?limit=${limit}`);
}

// === Financials (5y annual + quarterly) ===

export interface ApiFinancialAnnual {
  symbol: string;
  year: number;
  sales: number | null;
  cogs: number | null;
  gp: number | null;
  op_income: number | null;
  net_income: number | null;
  eps: number | null;
  total_assets: number | null;
  total_equity: number | null;
  total_debt: number | null;
  current_assets: number | null;
  current_liabilities: number | null;
  gpm: number | null;
  npm: number | null;
  roe: number | null;
  roa: number | null;
  refreshed_at?: string;
}

export interface ApiFinancialQuarterly {
  symbol: string;
  period: string;
  end_date: string | null;
  sales: number | null;
  net_income: number | null;
  eps: number | null;
  refreshed_at?: string;
}

export function fetchAnnualFinancials(symbol: string, limit = 10): Promise<ApiFinancialAnnual[]> {
  return get<ApiFinancialAnnual[]>(`/api/financials/${symbol}/annual?limit=${limit}`);
}

export function fetchQuarterlyFinancials(
  symbol: string,
  limit = 20,
): Promise<ApiFinancialQuarterly[]> {
  return get<ApiFinancialQuarterly[]>(`/api/financials/${symbol}/quarterly?limit=${limit}`);
}
