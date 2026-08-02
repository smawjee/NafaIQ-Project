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

export function toLegacySignal(signal: ApiSignalDetail): ApiSignal {
  return {
    symbol: signal.symbol,
    signal: ratingToLegacySignal(signal.technical_setup.rating),
    confidence: 0,
    probabilities: {},
    features_used: signal.technical_setup.components.map((component) => component.name),
    model_version: signal.technical_setup.version,
  };
}
