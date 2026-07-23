import { render } from "@testing-library/react-native";
import React from "react";

import { SignalContextTiles } from "@/components/psx/SignalContextTiles";
import { ThemeProvider } from "@/hooks/use-theme";
import type { ApiSignalV2 } from "@nafaiq/shared";

function makeSignal(overrides: Partial<ApiSignalV2> = {}): ApiSignalV2 {
  return {
    symbol: "HBL",
    horizon: "20D",
    signal: "BUY",
    confidence: 64,
    rank_score: 0.7,
    technical_signal: "BUY",
    technical_score: 0.55,
    ml_signal: null,
    ml_confidence: null,
    risk_level: "MODERATE",
    regime: "BULLISH",
    freshness: "LIVE",
    reasons: [],
    warnings: [],
    indicator_votes: [],
    probabilities: null,
    features_snapshot: {},
    model_version: "v3",
    engine_version: "3.2",
    predicted_at: "2026-07-23T09:00:00Z",
    ...overrides,
  };
}

function renderTiles(signal: ApiSignalV2) {
  return render(
    <ThemeProvider>
      <SignalContextTiles signal={signal} />
    </ThemeProvider>,
  );
}

describe("SignalContextTiles", () => {
  it("renders nothing when the signal has no context blocks", () => {
    const { toJSON } = renderTiles(makeSignal());
    expect(toJSON()).toBeNull();
  });

  it("renders consensus, trend and flow tiles from a fully-populated signal", () => {
    const { getByText } = renderTiles(
      makeSignal({
        consensus: {
          rating: 0.4,
          ma_rating: 0.5,
          oscillator_rating: 0.2,
          label: "BUY",
          source: "tradingview",
          as_of: "2026-07-23",
        },
        consensus_agreement: "AGREES",
        trend_state: "UPTREND",
        trend_score: 0.8,
        risk_metrics: {
          annualized_volatility: 0.32,
          expected_20d_move_pct: 0.09,
          suggested_stop_pct: 0.055,
          position_risk: "MODERATE",
          continuation: null,
        },
        flow_context: {
          foreign_net_5d_pkr: 1_200_000_000,
          foreign_net_20d_pkr: -340_000_000,
          foreign_net_5d_usd: 4_300_000,
          trend: "FOREIGN_BUYING",
          last_date: "2026-07-22",
          days_covered: 20,
          source: "fipi",
        },
      }),
    );

    expect(getByText("External check")).toBeTruthy();
    expect(getByText("Aligned")).toBeTruthy();
    expect(getByText("Trend state")).toBeTruthy();
    expect(getByText("Uptrend")).toBeTruthy();
    expect(getByText("Stop 5.5% · Vol 32%")).toBeTruthy();
    expect(getByText("Foreign flow (FIPI)")).toBeTruthy();
    expect(getByText("Foreigners buying")).toBeTruthy();
    expect(getByText("5d +Rs 1.2B · 20d -Rs 340M")).toBeTruthy();
  });

  it("tones the flow tile bearish and skips absent tiles", () => {
    const { getByText, queryByText } = renderTiles(
      makeSignal({
        flow_context: {
          foreign_net_5d_pkr: -900_000_000,
          foreign_net_20d_pkr: -2_100_000_000,
          foreign_net_5d_usd: -3_200_000,
          trend: "FOREIGN_SELLING",
          last_date: "2026-07-22",
          days_covered: 20,
          source: "fipi",
        },
      }),
    );

    expect(getByText("Foreigners selling")).toBeTruthy();
    expect(queryByText("External check")).toBeNull();
    expect(queryByText("Trend state")).toBeNull();
  });
});
