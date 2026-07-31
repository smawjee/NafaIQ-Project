export type TechnicalSetupRating =
  "Strong Bullish" | "Bullish" | "Neutral" | "Bearish" | "Strong Bearish";

export interface ApiTechnicalComponent {
  name: string;
  vote: -1 | 0 | 1;
  value: number | null;
  reason: string;
}

export interface ApiTechnicalSetup {
  status: "available" | "unavailable";
  rating: TechnicalSetupRating | null;
  score: number | null;
  bar_date: string | null;
  coverage: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  components: ApiTechnicalComponent[];
  version: string;
  reason_code: string | null;
}

export interface ApiForecastOutlook {
  status: "published" | "shadow" | "abstained" | "stale" | "unavailable";
  direction: "OUTPERFORM" | "UNDERPERFORM" | null;
  horizon_sessions: number;
  event_source: {
    event_type?: string;
    title?: string;
    published_at?: string;
    source_url?: string;
  } | null;
  p_outperform: number | null;
  expected_excess_net: number | null;
  interval: { lower: number; upper: number } | null;
  issued_at: string | null;
  expires_at: string | null;
  model_version: string | null;
  abstain_reason: string | null;
  headline: string;
}

export interface ApiCorporateEvent {
  event_type: "EARNINGS" | "DIVIDEND" | "INSIDER" | "MATERIAL" | "OTHER";
  title: string;
  published_at: string | null;
  period_end: string | null;
  source_url: string | null;
}

export interface ApiEarningsSummary {
  as_of_period: string | null;
  eps_latest: number | null;
  eps_change: number | null;
  earnings_surprise: number | null;
  eps_ttm: number | null;
  eps_ttm_growth: number | null;
  profitability_quality: number | null;
  quarters_available: number;
}

export interface ApiRelativeRank {
  composite_percentile: number | null;
  universe_size: number | null;
  as_of: string | null;
  factors: Record<string, number>;
}

export interface ApiQualityScore {
  score: number;
  label: "High" | "Moderate" | "Low";
  drivers: string[];
}

export interface ApiMarketContext {
  trend_state: string | null;
  trend_score: number | null;
  regime: string | null;
  risk_level: string | null;
  liquidity_score: number | null;
  volatility_score: number | null;
  relative_rank: ApiRelativeRank | null;
  flow: {
    trend?: string;
    foreign_net_5d_pkr?: number;
    foreign_net_20d_pkr?: number;
    foreign_net_5d_usd?: number;
    last_date?: string;
    days_covered?: number;
  } | null;
  risk_metrics: {
    annualized_volatility?: number;
    expected_20d_move_pct?: number;
    suggested_stop_pct?: number;
    position_risk?: string;
    continuation?: {
      p_negative_20d?: number;
      p_positive_20d?: number;
      median_20d_return?: number;
      n?: number;
    } | null;
  } | null;
  rating_base_rate: {
    rating?: string;
    horizon?: number;
    n?: number;
    p_up?: number;
    median_return?: number;
    mean_return?: number;
    p10?: number;
    p90?: number;
  } | null;
  recent_events: ApiCorporateEvent[];
  earnings: ApiEarningsSummary | null;
  warnings: string[];
}

export interface ApiSignalV4 {
  symbol: string;
  as_of: string;
  technical_setup: ApiTechnicalSetup;
  quality: ApiQualityScore | null;
  forecast: ApiForecastOutlook;
  context: ApiMarketContext;
  disclosure: string;
  data_quality: Record<string, unknown>;
}

export interface BatchSignalsV4Response {
  signals: ApiSignalV4[];
  count: number;
  contract: "signals-v4";
}
