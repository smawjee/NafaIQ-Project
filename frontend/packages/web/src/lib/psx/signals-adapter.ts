import type { ApiSignal, BatchSignalsResponse } from "./types";
import type { ApiSignalDetail, BatchSignalsDetailResponse } from "./signals";

function legacyLabel(rating: string | null): ApiSignal["signal"] {
  if (rating === "Strong Bullish") return "STRONG BUY";
  if (rating === "Bullish") return "BUY";
  if (rating === "Bearish") return "SELL";
  if (rating === "Strong Bearish") return "STRONG SELL";
  if (rating === "Neutral") return "HOLD";
  return "NO SIGNAL";
}

export function toLegacySignal(signal: ApiSignalDetail): ApiSignal {
  return {
    symbol: signal.symbol,
    signal: legacyLabel(signal.technical_setup.rating),
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
