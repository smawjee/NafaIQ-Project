import type { ApiSignal } from "@nafaiq/shared";

export interface ApiSignalV4 {
  symbol: string;
  as_of: string;
  technical_setup: {
    status: "available" | "unavailable";
    rating: "Strong Bullish" | "Bullish" | "Neutral" | "Bearish" | "Strong Bearish" | null;
    score: number | null;
    bar_date: string | null;
    coverage: number;
    bullish_count: number;
    bearish_count: number;
    neutral_count: number;
    components: Array<{ name: string; vote: -1 | 0 | 1; value: number | null; reason: string }>;
    version: string;
    reason_code: string | null;
  };
  forecast: {
    status: "published" | "shadow" | "abstained" | "stale" | "unavailable";
    direction: "OUTPERFORM" | "UNDERPERFORM" | null;
    horizon_sessions: number;
    p_outperform: number | null;
    expected_excess_net: number | null;
    interval: { lower: number; upper: number } | null;
    abstain_reason: string | null;
  };
  data_quality: Record<string, unknown>;
}

export function toLegacySignal(signal: ApiSignalV4): ApiSignal {
  const rating = signal.technical_setup.rating;
  const legacy = rating === "Strong Bullish" ? "STRONG BUY" : rating === "Bullish" ? "BUY" : rating === "Bearish" ? "SELL" : rating === "Strong Bearish" ? "STRONG SELL" : rating === "Neutral" ? "HOLD" : "NO SIGNAL";
  return {
    symbol: signal.symbol,
    signal: legacy,
    confidence: 0,
    probabilities: {},
    features_used: signal.technical_setup.components.map((component) => component.name),
    model_version: signal.technical_setup.version,
  };
}

