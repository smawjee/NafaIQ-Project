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
  sector?: string;
  price: number;
  change_pct: number;
  volume: number;
  /** Real market cap, or null when listed_shares is unknown. Never a proxy. */
  market_cap: number | null;
  /** Value used to size the tile — a real cap or a volume proxy. Not a cap. */
  size_metric: number;
  sizing_basis: "market_cap" | "volume_proxy";
  logoid?: string | null;
}

export interface ApiTreemapSector {
  name: string;
  avg_change_pct: number;
  /** Null unless every stock in the sector had a real market cap. */
  total_market_cap: number | null;
  total_size_metric: number;
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
  code: string;
  name: string;
  value: number;
  change: number;
  changePct: number;
  date?: string | null;
}

export interface UiSector {
  name: string;
  pct: number;
  volume: number;
}

export type Signal = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL" | "NO SIGNAL";

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

export type SignalHorizon = "5D" | "20D" | "60D";

export interface ApiIndicatorVote {
  name: string;
  vote: -1 | 0 | 1;
  weight: number;
  value: number | null;
  reason: string;
}

export interface ApiSignalV2 {
  symbol: string;
  horizon: SignalHorizon;
  signal: Signal;
  confidence: number;
  rank_score: number;
  technical_signal: Signal;
  technical_score: number;
  ml_signal: Signal | null;
  ml_confidence: number | null;
  risk_level: "LOW" | "MODERATE" | "HIGH" | "EXTREME";
  regime: "BULLISH" | "NEUTRAL" | "BEARISH" | "HIGH_VOLATILITY";
  freshness: "LIVE" | "DELAYED" | "STALE" | "UNKNOWN";
  reasons: string[];
  warnings: string[];
  indicator_votes: ApiIndicatorVote[];
  probabilities: Record<string, number> | null;
  features_snapshot: Record<string, unknown>;
  model_version: string;
  engine_version: string;
  predicted_at: string;
  consensus?: ApiSignalConsensus | null;
  consensus_agreement?: "AGREES" | "MIXED" | "DISAGREES" | null;
  trend_state?: "UPTREND" | "WEAKENING" | "DOWNTREND" | "BASING" | "RANGE" | "UNKNOWN" | null;
  trend_score?: number | null;
  risk_metrics?: ApiSignalRiskMetrics | null;
  flow_context?: ApiFlowContext | null;
}

export type ConsensusLabel = "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL";

export interface ApiSignalConsensus {
  rating: number;
  ma_rating: number | null;
  oscillator_rating: number | null;
  label: ConsensusLabel | null;
  source: string;
  as_of: string;
}

export interface ApiSignalRiskMetrics {
  annualized_volatility: number;
  expected_20d_move_pct: number;
  suggested_stop_pct: number;
  position_risk: "LOW" | "MODERATE" | "HIGH" | "EXTREME";
  continuation: {
    n: number;
    p_negative_20d: number;
    median_20d_return: number;
  } | null;
}

export interface ApiFlowContext {
  foreign_net_5d_pkr: number;
  foreign_net_20d_pkr: number;
  foreign_net_5d_usd: number;
  trend: "FOREIGN_BUYING" | "FOREIGN_SELLING" | "MIXED" | "NEUTRAL";
  last_date: string;
  days_covered: number;
  source: string;
}

export interface BatchSignalsV2Response {
  signals: ApiSignalV2[];
  count: number;
}

export interface ApiTrackRecordEntry {
  n: number;
  hit_rate: number;
  avg_return: number;
  avg_excess: number;
  large_loss_rate: number;
  avoided_loss_rate?: number;
}

export interface ApiTrackRecord {
  matured_total: number;
  by_signal: Record<string, ApiTrackRecordEntry>;
  pending_maturity: number;
  note: string;
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
