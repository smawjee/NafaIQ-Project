export interface ApiMarketSnapshotItem {
  id: number;
  symbol: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  day_high: number | null;
  day_low: number | null;
  refreshed_at: string;
}

export interface ApiOHLCVBar {
  id: number;
  symbol: string;
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface ApiSignal {
  symbol: string;
  signal: string;
  confidence: number;
  probabilities?: Record<string, number>;
  model_version?: string;
}

export interface BatchSignalsResponse {
  signals: ApiSignal[];
}

export interface ApiSymbolInfo {
  symbol: string;
  name: string;
  sector: string | null;
}

export interface ApiCompanyProfile {
  symbol: string;
  name: string;
  sector: string | null;
  listed_shares: number | null;
  free_float: number | null;
  refreshed_at: string;
}

export interface ApiFundamentalsData {
  symbol: string;
  eps: number | null;
  pe: number | null;
  pb: number | null;
  div_yield: number | null;
  payout: number | null;
  roe: number | null;
  refreshed_at: string;
}

export interface ApiAnnouncementItem {
  id: string;
  symbol: string | null;
  posted_at: string;
  title: string;
  category: string | null;
  url: string | null;
}

export interface ApiDividendEvent {
  announcement_id: string;
  symbol: string;
  ex_date: string | null;
  announcement_date: string | null;
  payout_type: string | null;
  per_share: number | null;
  bonus_pct: number | null;
}

export interface ApiIndexBar {
  code: string;
  date: string;
  close: number | null;
  volume: number | null;
}

export interface ApiSectorDataItem {
  sector: string;
  avg_change_pct: number;
  stock_count: number;
  total_volume: number;
}

export interface ApiIndicatorPayload {
  symbol: string;
  indicators: Record<string, number | Record<string, number>>;
}

export interface ScreenerRequest {
  sector?: string;
  min_pe?: number;
  max_pe?: number;
  min_volume?: number;
  min_price?: number;
  max_price?: number;
  rsi_min?: number;
  rsi_max?: number;
  limit?: number;
}

export interface ScreenerResponse {
  results: unknown[];
  count: number;
}

export interface BacktestRequest {
  filter_spec?: unknown;
  initial_capital?: number;
  start_date?: string;
  end_date?: string;
}

export interface ApiBacktestResult {
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  trades: unknown[];
}
