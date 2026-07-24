import { API_BASE_URL } from "@/lib/api";

import type {
  ApiTrackRecord,
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
  ApiSignalV2,
  BatchSignalsResponse,
  BatchSignalsV2Response,
  SignalHorizon,
  ScreenerRequest,
  ScreenerResponse,
  BacktestRequest,
  ApiBacktestResult,
  ApiMutualFund,
  ApiFundNavHistory,
} from "./types";
import type { ApiSignalV4, BatchSignalsV4Response } from "./signals-v4";
import { toLegacyBatch, toLegacySignal } from "./signals-v4-adapter";

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
  return get<ApiSignalV4>(`/api/signal/${symbol}`).then(toLegacySignal);
}

export function fetchSignalV4(symbol: string): Promise<ApiSignalV4> {
  return get<ApiSignalV4>(`/api/signals/v3/${symbol}`);
}

export function fetchBatchSignalsV4(limit = 50): Promise<BatchSignalsV4Response> {
  return post<BatchSignalsV4Response>("/api/signals/v3/batch", { limit });
}

export function fetchBatchSignals(limit = 50): Promise<BatchSignalsResponse> {
  return post<BatchSignalsV4Response>("/api/signals/batch", { limit }).then(toLegacyBatch);
}

export function fetchSignalV2(
  symbol: string,
  horizon: SignalHorizon = "20D",
): Promise<ApiSignalV2> {
  return get<ApiSignalV2>(`/api/signals/v2/${symbol}?horizon=${horizon}`);
}

export function fetchBatchSignalsV2(
  limit = 50,
  horizon: SignalHorizon = "20D",
): Promise<BatchSignalsV2Response> {
  return post<BatchSignalsV2Response>("/api/signals/v2/batch", { limit, horizon });
}

export function fetchSignalTrackRecord(): Promise<ApiTrackRecord> {
  return get<ApiTrackRecord>("/api/signals/v2/track-record");
}

export function fetchSignalLeaderboardV2(
  limit = 50,
  horizon: SignalHorizon = "20D",
): Promise<BatchSignalsV2Response> {
  return get<BatchSignalsV2Response>(
    `/api/signals/v2/leaderboard?horizon=${horizon}&limit=${limit}`,
  );
}

// === User-authenticated request exports ===
export { userGet, userPost, userPatch, userDelete };

// === Bulk "delete all" (user-scoped; server deletes only the caller's rows) ===
export function deleteAllFinance(
  entity: "transactions" | "bills" | "goals" | "budgets",
): Promise<{ deleted: number; entity: string }> {
  return userDelete<{ deleted: number; entity: string }>(`/api/finance/${entity}`);
}

export function clearWatchlist(): Promise<{ deleted: number }> {
  return userDelete<{ deleted: number }>("/api/watchlist");
}

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

export interface ApiMonetaryCurrency {
  code: string;
  name: string;
  per_usd: number;
  one_unit_in_pkr: number;
  one_pkr_in_unit: number;
}

export interface ApiMonetaryMetal {
  code: "XAU" | "XAG";
  name: string;
  basis: string;
  usd_per_troy_oz: number;
  pkr_per_gram: number;
  pkr_per_10g: number;
  pkr_per_tola: number;
  source_name?: string | null;
  source_url?: string | null;
  cadence?: string | null;
  as_of?: string | null;
  city?: string | null;
}

export interface ApiMonetarySnapshot {
  base: "USD";
  as_of: string | null;
  refreshed_at: string;
  expires_at: string;
  ttl_seconds: number;
  source: {
    name: string;
    url: string;
    cadence: string;
  };
  metal_source: {
    name: string;
    url: string;
    cadence: string;
    as_of?: string | null;
    city?: string | null;
  } | null;
  usd_pkr: number;
  rates: Record<string, number>;
  currencies: ApiMonetaryCurrency[];
  metals: ApiMonetaryMetal[];
  validation: {
    status: "cross_checked" | "single_source" | "review";
    max_deviation_pct: number;
    message: string;
    checked_against: Array<{
      name: string;
      usd_pkr: number;
      deviation_pct: number;
      cadence: string;
      official: boolean;
    }>;
  };
  warnings: string[];
  disclaimer: string;
  stale: boolean;
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

export function fetchMonetarySnapshot(refresh = false): Promise<ApiMonetarySnapshot> {
  return get<ApiMonetarySnapshot>(`/api/macro/monetary${refresh ? "?refresh=true" : ""}`);
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

// === Learn Hub search (RAG) ===

export interface ApiLearnStatus {
  enabled: boolean;
}

export interface ApiLearnSearchResult {
  /** null on glossary_term rows — they belong to no lesson. Verified against
   * the live API, which returns lesson_id: null for every glossary hit. */
  lesson_id: string | null;
  section_id: string | null;
  source_type:
    "lesson_section" | "lesson_overview" | "glossary_term" | "quiz_explanation" | "learning_path";
  title: string;
  heading: string | null;
  snippet_en: string;
  snippet_ur: string | null;
  score: number;
}

export interface ApiLearnSearchResponse {
  results: ApiLearnSearchResult[];
}

export function fetchLearnStatus(): Promise<ApiLearnStatus> {
  return get<ApiLearnStatus>("/api/learn/status");
}

export function searchLearn(
  q: string,
  lang: "en" | "ur",
  limit = 8,
): Promise<ApiLearnSearchResponse> {
  const params = new URLSearchParams();
  params.set("q", q);
  params.set("lang", lang);
  params.set("limit", String(limit));
  return get<ApiLearnSearchResponse>(`/api/learn/search?${params.toString()}`);
}

/** Glossary-only search: exact terms land via keyword match, concepts via
 * embedding similarity. Same result shape as searchLearn. */
export function searchLearnGlossary(
  q: string,
  lang: "en" | "ur",
  limit = 5,
): Promise<ApiLearnSearchResponse> {
  const params = new URLSearchParams();
  params.set("q", q);
  params.set("lang", lang);
  params.set("limit", String(limit));
  return get<ApiLearnSearchResponse>(`/api/learn/glossary/search?${params.toString()}`);
}

export interface ApiLearnRelated {
  lesson_id: string;
  score: number;
}

export interface ApiLearnRelatedResponse {
  results: ApiLearnRelated[];
}

/** Related lessons by content similarity. Precomputed server-side at ingest,
 * so this is a plain lookup — no embedding round-trip on the lesson page. */
export function fetchLearnRelated(lessonId: string, limit = 4): Promise<ApiLearnRelatedResponse> {
  const params = new URLSearchParams();
  params.set("lesson_id", lessonId);
  params.set("limit", String(limit));
  return get<ApiLearnRelatedResponse>(`/api/learn/related?${params.toString()}`);
}

// === Learn quiz AI explanation (user-scoped) ===

export interface ApiQuizExplanation {
  /** null is a normal response — retrieval found nothing to ground on, so the
   * caller keeps its static explanation. Not an error. */
  explanation: string | null;
  /** Cited section headings, possibly empty. */
  sources: string[];
}

/**
 * Grounded, in-depth explanation of one quiz question. Quiz questions have no
 * stable ids (they're shuffled at render), so the question and option TEXT are
 * what the server retrieves against. Spends the caller's daily AI budget — fire
 * only on an explicit learner action.
 */
export function fetchQuizExplanation(body: {
  lessonId: string;
  question: string;
  selectedOption: string;
  correctOption: string;
  lang: "en" | "ur";
}): Promise<ApiQuizExplanation> {
  return userPost<ApiQuizExplanation>("/api/learn/ai/quiz-explanation", body);
}

// === Learn lesson AI summary (user-scoped) ===

export interface ApiLessonSummary {
  /** Grounded takeaways. An empty list is a normal response — retrieval found
   * nothing to summarise — so the caller renders nothing. Not an error. */
  key_ideas: string[];
  /** Key terms worth remembering, possibly empty. */
  terms: string[];
  /** The single most common misunderstanding, or null when there isn't one. */
  pitfall: string | null;
  /** Cited section headings, possibly empty. */
  sources: string[];
}

/**
 * Grounded summary of a lesson, or of one section when `sectionId` is given.
 * Spends the caller's daily AI budget — fire only on an explicit learner
 * action, never on page load.
 */
export function fetchLessonSummary(body: {
  lessonId: string;
  sectionId?: string;
  lang: "en" | "ur";
}): Promise<ApiLessonSummary> {
  return userPost<ApiLessonSummary>("/api/learn/ai/summary", body);
}
