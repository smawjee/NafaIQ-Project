// DTO contracts for the NafaIQ Python (FastAPI) backend.
// Mirrors frontend/packages/web/src/lib/psx/types.ts — the web client is the
// reference implementation; keep the two in sync when endpoints change.

import type { Signal } from "./data";

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

/* ── Signal breakdown (optional detail fields on list rows) ─────────────── */

export type SignalHorizon = "5D" | "20D" | "60D";

/** v2 can decline to call a setup; the 5-value `Signal` stays badge-safe. */
export type SignalLabel = Signal | "NO SIGNAL";

export interface ApiIndicatorVote {
  name: string;
  vote: -1 | 0 | 1;
  weight: number;
  value: number | null;
  reason: string;
}

/** TradingView technical-rating consensus used as an external cross-check. */
export interface ApiSignalConsensus {
  rating: number;
  ma_rating: number | null;
  oscillator_rating: number | null;
  label: string | null;
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

/** Market-wide FIPI foreign-flow summary attached to every v2 signal. */
export interface ApiFlowContext {
  foreign_net_5d_pkr: number;
  foreign_net_20d_pkr: number;
  foreign_net_5d_usd: number;
  trend: "FOREIGN_BUYING" | "FOREIGN_SELLING" | "MIXED" | "NEUTRAL";
  last_date: string;
  days_covered: number;
  source: string;
}

export interface ApiSignalBreakdown {
  symbol: string;
  horizon: SignalHorizon;
  signal: SignalLabel;
  confidence: number;
  rank_score: number;
  technical_signal: SignalLabel;
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
  consensus?: ApiSignalConsensus | null;
  consensus_agreement?: "AGREES" | "MIXED" | "DISAGREES" | null;
  trend_state?: "UPTREND" | "WEAKENING" | "DOWNTREND" | "BASING" | "RANGE" | "UNKNOWN" | null;
  trend_score?: number | null;
  risk_metrics?: ApiSignalRiskMetrics | null;
  flow_context?: ApiFlowContext | null;
  features_snapshot: Record<string, unknown>;
  model_version: string;
  engine_version: string;
  predicted_at: string;
}

/* ── Signal track record (/api/signals/track-record) ────────────────────── */

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
  /** Keys are underscore signal labels ("STRONG_BUY"), per the outcomes store. */
  by_signal: Record<string, ApiTrackRecordEntry>;
  pending_maturity: number;
  note: string;
}
