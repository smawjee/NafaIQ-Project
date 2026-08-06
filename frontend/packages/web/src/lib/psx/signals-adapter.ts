import type { ApiSignal, BatchSignalsResponse } from "./types";
import type { ApiSignalDetail, BatchSignalsDetailResponse } from "./signals";

/** Indicator posture -> badge. Fallback only; see toLegacySignal. */
function legacyLabel(rating: string | null): ApiSignal["signal"] {
  if (rating === "Strong Bullish") return "STRONG BUY";
  if (rating === "Bullish") return "BUY";
  if (rating === "Bearish") return "SELL";
  if (rating === "Strong Bearish") return "STRONG SELL";
  if (rating === "Neutral") return "HOLD";
  return "NO SIGNAL";
}

/** Calibrated call -> badge. */
function recommendationLabel(
  rating: NonNullable<ApiSignalDetail["recommendation"]>["rating"],
): ApiSignal["signal"] {
  if (rating === "STRONG_BUY") return "STRONG BUY";
  if (rating === "BUY") return "BUY";
  if (rating === "SELL") return "SELL";
  if (rating === "STRONG_SELL") return "STRONG SELL";
  return "HOLD";
}

export function toLegacySignal(signal: ApiSignalDetail): ApiSignal {
  return {
    symbol: signal.symbol,
    // Prefer the calibrated call over the raw indicator posture.
    //
    // `legacyLabel` maps "Strong Bullish" -> "STRONG BUY", which is the exact
    // claim the research disproved: across 339,683 PSX observations a bullish
    // posture is followed by *below*-average returns (see
    // backend/scripts/signals/RESEARCH_LOG.md). Rendering posture in a slot
    // labelled BUY/SELL asserts a direction the data contradicts.
    //
    // Falls back to posture when no recommendation exists, so symbols without
    // enough history behave exactly as before.
    signal: signal.recommendation
      ? recommendationLabel(signal.recommendation.rating)
      : legacyLabel(signal.technical_setup.rating),
    confidence: 0,
    probabilities: {},
    features_used: signal.technical_setup.components.map((component) => component.name),
    model_version: signal.technical_setup.version,
  };
}

export function toLegacyBatch(signal: BatchSignalsDetailResponse): BatchSignalsResponse {
  return {
    signals: signal.signals.map(toLegacySignal),
    count: signal.count,
  };
}
