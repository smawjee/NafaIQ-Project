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

export type RecommendationRating = "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL";

/**
 * Tier 1 calibrated call. `p` is a *measured historical frequency* for the
 * cohort named in `basis` — how often stocks in that state rose over the
 * horizon — not a model score and not a forecast.
 *
 * Two things the UI must not get wrong:
 *  - `base_rate` is the bar, NOT 0.5. The measured PSX 20-session rate is
 *    ~0.472, so a stock at p = 0.50 is merely typical. Always render `p`
 *    against `base_rate`, never against a half.
 *  - `p_lower`/`p_upper` are a 95% Wilson interval. A wide interval is why a
 *    promising-looking `p` still reads HOLD; show the band, not just the point.
 */
export interface ApiRecommendation {
  rating: RecommendationRating;
  horizon_sessions: number;
  p: number | null;
  p_lower: number | null;
  p_upper: number | null;
  base_rate: number | null;
  /** Plain-language statement of what `p` is the probability of. */
  event: string;
  /** The cohort that answered, e.g. "stocks after a large recent decline". */
  basis: string | null;
  sample_size: number;
  expected_move: number | null;
  round_trip_cost: number | null;
  suggested_stop_pct: number | null;
  drivers: string[];
  /** Present on every HOLD; names the bar that was not cleared. */
  abstain_reason: string | null;
  /** Buy calls face a wider bar than sell calls — the sell-side evidence is stronger. */
  asymmetric: boolean;
}

export interface ApiSignalDetail {
  symbol: string;
  as_of: string;
  technical_setup: ApiTechnicalSetup;
  quality: ApiQualityScore | null;
  /** Null when no technical setup is available, so no cohort can be assigned. */
  recommendation: ApiRecommendation | null;
  forecast: ApiForecastOutlook;
  context: ApiMarketContext;
  disclosure: string;
  data_quality: Record<string, unknown>;
}

export interface BatchSignalsDetailResponse {
  signals: ApiSignalDetail[];
  count: number;
  contract: "signals";
}
