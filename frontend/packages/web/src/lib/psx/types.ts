export interface ApiMarketSnapshotItem {
  symbol: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number;
  day_high: number | null;
  day_low: number | null;
}

export interface ApiOHLCVBar {
  symbol: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ApiSymbolInfo {
  symbol: string;
  name: string;
  sector: string | null;
  logoid?: string | null;
}

export interface ApiCompanyProfile {
  symbol: string;
  name: string;
  sector: string | null;
  listed_shares: number | null;
  free_float: number | null;
}

export interface ApiFundamentalsData {
  symbol: string;
  eps: number | null;
  pe: number | null;
  pb: number | null;
  div_yield: number | null;
  payout: number | null;
  roe: number | null;
}

export interface ApiAnnouncementItem {
  id: string;
  symbol: string | null;
  posted_at: string | null;
  title: string;
  category: string | null;
  url: string | null;
}

export interface ApiDividendEvent {
  announcement_id: string;
  symbol: string;
  ex_date: string | null;
  announcement_date: string | null;
  payout_type: string;
  per_share: number | null;
  bonus_pct: number | null;
}

export interface ApiIndexBar {
  code: string;
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number | null;
}

export interface ApiIndexCard {
  code: string;
  date: string | null;
  close: number;
  prev_close: number | null;
  change: number;
  change_pct: number;
}

export interface ApiScreenerMetric {
  symbol: string;
  rsi: number | null;
  market_cap: number | null;
}

export interface ApiSectorDataItem {
  name: string;
  pct: number;
  volume: number | null;
  value: number | null;
}

export interface ApiHeatmapStockItem {
  symbol: string;
  name: string;
  sector: string;
  close: number;
  change_pct: number;
  volume: number;
  market_cap: number | null;
}

export interface ApiHeatmapResponse {
  source: string;
  sectors: ApiSectorDataItem[];
  stocks: ApiHeatmapStockItem[];
  count: number;
}

export interface ApiTreemapStock {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  market_cap: number;
  logoid?: string | null;
}

export interface ApiTreemapSector {
  name: string;
  avg_change_pct: number;
  total_market_cap: number;
  stock_count: number;
  stocks: ApiTreemapStock[];
}

export interface ApiTreemap {
  as_of: string;
  sectors: ApiTreemapSector[];
  stock_count: number;
}

export interface ApiIndicatorPayload {
  symbol: string;
  indicators: Record<string, number | null>;
}

export interface ScreenerResultRow {
  symbol: string;
  price: number | null;
  change_pct: number | null;
  volume: number;
  sector: string | null;
  signal: string | null;
  rsi: number | null;
}

export interface ScreenerResponse {
  results: ScreenerResultRow[];
  count: number;
}

export interface ScreenerRequest {
  sector?: string;
  pe_max?: number;
  roe_min?: number;
  pb_max?: number;
  div_yield_min?: number;
  above_sma200?: boolean;
  rsi_max?: number;
  rsi_min?: number;
  sort_by?: string;
  desc?: boolean;
  limit?: number;
}

export interface BacktestRequest {
  filter_spec: Record<string, unknown>;
  hold_days?: number;
  since?: string;
}

export interface ApiBacktestResult {
  avg_return: number;
  median_return: number;
  kse_return: number;
  winners: number;
  losers: number;
  matched_symbols: number;
}

export interface UiTicker {
  symbol: string;
  name: string;
  sector: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
}

export interface UiIndex {
  name: string;
  value: number;
  change: number;
  changePct: number;
}

export interface UiSector {
  name: string;
  pct: number;
  volume: number;
}

export type Signal = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";

export interface ApiSignal {
  symbol: string;
  signal: Signal;
  confidence: number;
  probabilities: Record<string, number>;
  features_used: string[];
  model_version: string;
}

export interface BatchSignalsResponse {
  signals: ApiSignal[];
  count: number;
}
export interface ApiMutualFund {
  fund_code: string;
  name: string;
  category: string | null;
  amc: string | null;
  shariah: boolean;
  latest_nav: number | null;
  nav_date: string | null;
  aum: number | null;
  refreshed_at?: string;
}

export interface ApiFundNavHistory {
  fund_code: string;
  date: string;
  nav: number | null;
}
