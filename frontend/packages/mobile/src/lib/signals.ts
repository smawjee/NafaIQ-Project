import type { ApiSignal } from "@nafaiq/shared";

/** Rating labels the engine emits, strongest bullish first. */
export type SignalRating =
  | "Strong Bullish"
  | "Bullish"
  | "Neutral"
  | "Bearish"
  | "Strong Bearish";

export interface ApiSignalDetail {
  symbol: string;
  as_of: string;
  technical_setup: {
    status: "available" | "unavailable";
    rating: SignalRating | null;
    score: number | null;
    bar_date: string | null;
    coverage: number;
    bullish_count: number;
    bearish_count: number;
    neutral_count: number;
    components: { name: string; vote: -1 | 0 | 1; value: number | null; reason: string }[];
    version: string;
    reason_code: string | null;
  };
  /** Replaces the old confidence % — reliability of the measurement, not a direction. */
  quality: {
    score: number;
    label: "High" | "Moderate" | "Low";
    drivers: string[];
  } | null;
  forecast: {
    status: "published" | "shadow" | "abstained" | "stale" | "unavailable";
    direction: "OUTPERFORM" | "UNDERPERFORM" | null;
    horizon_sessions: number;
    p_outperform: number | null;
    expected_excess_net: number | null;
    interval: { lower: number; upper: number } | null;
    abstain_reason: string | null;
  };
  /** Descriptive market context — posture and measured base rates, never a call. */
  context?: {
    trend_state?: string | null;
    trend_score?: number | null;
    regime?: string | null;
    risk_level?: string | null;
    liquidity_score?: number | null;
    volatility_score?: number | null;
    risk_metrics?: {
      annualized_volatility: number;
      expected_20d_move_pct: number;
      suggested_stop_pct: number;
      position_risk: string;
      continuation?: {
        n: number;
        p_negative_20d: number;
        median_20d_return: number;
      } | null;
    } | null;
    /** Market-wide FIPI foreign flow (not per-symbol). */
    flow?: {
      trend: string;
      foreign_net_5d_pkr: number;
      foreign_net_20d_pkr: number;
      last_date?: string;
    } | null;
    warnings?: string[];
  };
  /**
   * Calibrated base-rate call. `p` is a measured historical frequency for the
   * cohort in `basis`, not a model score. `base_rate` is the bar to compare
   * against — it is ~0.47 on PSX, never 0.5.
   */
  recommendation?: {
    rating: "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL";
    horizon_sessions: number;
    p: number | null;
    p_lower: number | null;
    p_upper: number | null;
    base_rate: number | null;
    event: string;
    basis: string | null;
    sample_size: number;
    expected_move: number | null;
    round_trip_cost: number | null;
    suggested_stop_pct: number | null;
    drivers: string[];
    abstain_reason: string | null;
    asymmetric: boolean;
  } | null;
  disclosure?: string;
  data_quality: Record<string, unknown>;
}

/** Engine rating -> the 5-state badge label the shared UI already renders. */
export function ratingToLegacySignal(rating: SignalRating | null): ApiSignal["signal"] {
  switch (rating) {
    case "Strong Bullish":
      return "STRONG BUY";
    case "Bullish":
      return "BUY";
    case "Bearish":
      return "SELL";
    case "Strong Bearish":
      return "STRONG SELL";
    case "Neutral":
      return "HOLD";
    default:
      return "NO SIGNAL";
  }
}

/** Calibrated call -> the 5-state badge label the shared UI already renders. */
export function recommendationToBadge(
  rating: NonNullable<ApiSignalDetail["recommendation"]>["rating"],
): ApiSignal["signal"] {
  switch (rating) {
    case "STRONG_BUY":
      return "STRONG BUY";
    case "BUY":
      return "BUY";
    case "SELL":
      return "SELL";
    case "STRONG_SELL":
      return "STRONG SELL";
    default:
      return "HOLD";
  }
}

export function toLegacySignal(signal: ApiSignalDetail): ApiSignal {
  return {
    symbol: signal.symbol,
    // Prefer the calibrated call over the raw indicator posture.
    //
    // `ratingToLegacySignal` maps "Strong Bullish" -> "STRONG BUY", which is
    // the specific claim the research disproved: measured over 339,683 PSX
    // observations, a bullish posture is followed by *below*-average returns
    // (see backend/scripts/signals/RESEARCH_LOG.md). Showing the posture in a
    // slot labelled BUY/SELL asserts a direction the data contradicts.
    //
    // Falls back to the posture mapping when no recommendation is available,
    // so symbols without enough history behave exactly as before.
    signal: signal.recommendation
      ? recommendationToBadge(signal.recommendation.rating)
      : ratingToLegacySignal(signal.technical_setup.rating),
    confidence: 0,
    probabilities: {},
    features_used: signal.technical_setup.components.map((component) => component.name),
    model_version: signal.technical_setup.version,
  };
}
