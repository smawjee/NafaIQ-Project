import { render } from "@testing-library/react-native";
import React from "react";

import { SignalContextTiles } from "@/components/psx/SignalContextTiles";
import { ThemeProvider } from "@/hooks/use-theme";
import type { ApiSignalDetail } from "@/lib/signals";

function makeSignal(overrides: Partial<ApiSignalDetail> = {}): ApiSignalDetail {
  return {
    symbol: "HBL",
    as_of: "2026-07-23",
    technical_setup: {
      status: "available",
      rating: "Bullish",
      score: 0.55,
      bar_date: "2026-07-23",
      coverage: 1,
      bullish_count: 4,
      bearish_count: 1,
      neutral_count: 2,
      components: [],
      version: "technical-1",
      reason_code: null,
    },
    quality: null,
    forecast: {
      status: "unavailable",
      direction: null,
      horizon_sessions: 20,
      p_outperform: null,
      expected_excess_net: null,
      interval: null,
      abstain_reason: null,
    },
    data_quality: {},
    ...overrides,
  };
}

function renderTiles(signal: ApiSignalDetail) {
  return render(
    <ThemeProvider>
      <SignalContextTiles signal={signal} />
    </ThemeProvider>,
  );
}

describe("SignalContextTiles", () => {
  it("renders nothing when the signal has no quality or context blocks", () => {
    const { toJSON } = renderTiles(makeSignal());
    expect(toJSON()).toBeNull();
  });

  it("renders quality, trend and flow tiles from a fully-populated signal", () => {
    const { getByText } = renderTiles(
      makeSignal({
        quality: { score: 85, label: "High", drivers: [] },
        context: {
          trend_state: "UPTREND",
          trend_score: 0.8,
          risk_metrics: {
            annualized_volatility: 0.32,
            expected_20d_move_pct: 0.09,
            suggested_stop_pct: 0.055,
            position_risk: "MODERATE",
            continuation: null,
          },
          flow: {
            foreign_net_5d_pkr: 1_200_000_000,
            foreign_net_20d_pkr: -340_000_000,
            trend: "FOREIGN_BUYING",
            last_date: "2026-07-22",
          },
        },
      }),
    );

    expect(getByText("Signal quality")).toBeTruthy();
    expect(getByText("High")).toBeTruthy();
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
        context: {
          flow: {
            foreign_net_5d_pkr: -900_000_000,
            foreign_net_20d_pkr: -2_100_000_000,
            trend: "FOREIGN_SELLING",
            last_date: "2026-07-22",
          },
        },
      }),
    );

    expect(getByText("Foreigners selling")).toBeTruthy();
    expect(queryByText("Signal quality")).toBeNull();
    expect(queryByText("Trend state")).toBeNull();
  });
});
