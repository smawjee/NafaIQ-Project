import { render } from "@testing-library/react-native";
import React from "react";

import { SignalRecommendationCard } from "@/components/psx/SignalRecommendationCard";
import { ThemeProvider } from "@/hooks/use-theme";
import type { ApiSignalDetail } from "@/lib/signals";

type Recommendation = NonNullable<ApiSignalDetail["recommendation"]>;

function makeRecommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    rating: "BUY",
    horizon_sessions: 20,
    p: 0.535,
    p_lower: 0.52,
    p_upper: 0.551,
    base_rate: 0.472,
    event: "rose over the next 20 trading sessions",
    basis: "stocks after a large recent decline, in a trading range",
    sample_size: 3874,
    expected_move: 0.012,
    round_trip_cost: 0.0096,
    suggested_stop_pct: 0.08,
    drivers: [],
    abstain_reason: null,
    asymmetric: true,
    ...overrides,
  };
}

function makeSignal(overrides: Partial<ApiSignalDetail> = {}): ApiSignalDetail {
  return {
    symbol: "AIRLINK",
    as_of: "2026-08-05",
    technical_setup: {
      status: "available",
      rating: "Strong Bearish",
      score: -0.6,
      bar_date: "2026-08-05",
      coverage: 1,
      bullish_count: 2,
      bearish_count: 18,
      neutral_count: 6,
      components: [],
      version: "technical-v4.0",
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
    recommendation: makeRecommendation(),
    data_quality: {},
    ...overrides,
  };
}

function renderCard(signal?: ApiSignalDetail | null) {
  return render(
    <ThemeProvider>
      <SignalRecommendationCard signal={signal} />
    </ThemeProvider>,
  );
}

describe("SignalRecommendationCard", () => {
  it("renders the rating and the evidence behind it", () => {
    const { getByText } = renderCard(makeSignal());
    expect(getByText("Buy")).toBeTruthy();
    // Sample size must be visible: a probability without its n is not evidence.
    expect(getByText(/3,874/)).toBeTruthy();
  });

  it("shows the probability against the measured base rate, not 50%", () => {
    // The measured PSX 20-session rate is ~47%. Comparing to 50% would make an
    // ordinary stock look bearish, which is the specific trap this UI avoids.
    const { getByText } = renderCard(makeSignal());
    expect(getByText(/54% rose over the next/)).toBeTruthy();
    expect(getByText(/vs 47% typical/)).toBeTruthy();
  });

  it("shows the confidence interval so uncertainty is visible", () => {
    const { getByText } = renderCard(makeSignal());
    expect(getByText(/52%–55%/)).toBeTruthy();
    expect(getByText(/95% confidence/)).toBeTruthy();
  });

  it("bridges the gap when indicator posture disagrees with the call", () => {
    // Strong Bearish posture + BUY call is the common PSX case; unexplained it
    // reads as a self-contradiction.
    const { getByText } = renderCard(makeSignal());
    expect(getByText(/what happened next/i)).toBeTruthy();
  });

  it("does not show the bridge line when posture and call agree", () => {
    const signal = makeSignal({
      technical_setup: {
        ...makeSignal().technical_setup,
        rating: "Bullish",
      },
    });
    const { queryByText } = renderCard(signal);
    expect(queryByText(/what happened next/i)).toBeNull();
  });

  it("explains every HOLD rather than leaving it bare", () => {
    const signal = makeSignal({
      recommendation: makeRecommendation({
        rating: "HOLD",
        abstain_reason: "INTERVAL_STRADDLES_BASE_RATE",
      }),
    });
    const { getByText } = renderCard(signal);
    expect(getByText(/no clear edge either way/i)).toBeTruthy();
  });

  it("renders nothing when there is no recommendation", () => {
    const { toJSON } = renderCard(makeSignal({ recommendation: null }));
    expect(toJSON()).toBeNull();
  });

  it("renders nothing without a signal", () => {
    expect(renderCard(null).toJSON()).toBeNull();
  });

  it("survives a recommendation with no numbers", () => {
    const signal = makeSignal({
      recommendation: makeRecommendation({
        rating: "HOLD",
        p: null,
        p_lower: null,
        p_upper: null,
        base_rate: null,
        round_trip_cost: null,
        suggested_stop_pct: null,
        abstain_reason: "NO_CALIBRATION_DATA",
      }),
    });
    const { getByText } = renderCard(signal);
    expect(getByText("Hold")).toBeTruthy();
  });

  it("exposes the rating to screen readers", () => {
    const { getByLabelText } = renderCard(makeSignal());
    expect(getByLabelText(/Recommendation: Buy/i)).toBeTruthy();
  });

  it("discloses that buy calls face a higher bar", () => {
    const { getByText } = renderCard(makeSignal());
    expect(getByText(/Buy calls require stronger evidence/i)).toBeTruthy();
  });
});
