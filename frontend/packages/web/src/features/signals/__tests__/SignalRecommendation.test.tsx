import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SignalRecommendation } from "@/features/signals/SignalRecommendation";
import type { ApiRecommendation, ApiTechnicalSetup } from "@/lib/psx/signals";

function makeRecommendation(overrides: Partial<ApiRecommendation> = {}): ApiRecommendation {
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

function makeSetup(overrides: Partial<ApiTechnicalSetup> = {}): ApiTechnicalSetup {
  return {
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
    ...overrides,
  };
}

describe("SignalRecommendation", () => {
  it("renders the rating with the sample size behind it", () => {
    render(<SignalRecommendation recommendation={makeRecommendation()} setup={makeSetup()} />);
    expect(screen.getByText("Buy")).toBeInTheDocument();
    // A probability without its n is not evidence.
    expect(screen.getByText(/3,874 comparable cases/)).toBeInTheDocument();
  });

  it("compares the probability to the measured base rate, not to 50%", () => {
    // The measured PSX 20-session rate is ~47%. Anchoring the UI to 50% would
    // make a merely typical stock read as bearish.
    render(<SignalRecommendation recommendation={makeRecommendation()} setup={makeSetup()} />);
    expect(screen.getByText(/54% rose over the next/)).toBeInTheDocument();
    expect(screen.getByText(/vs 47% typical/)).toBeInTheDocument();
  });

  it("shows the confidence interval so uncertainty is visible", () => {
    render(<SignalRecommendation recommendation={makeRecommendation()} setup={makeSetup()} />);
    expect(screen.getByText(/Range 52%–55%/)).toBeInTheDocument();
    expect(screen.getByText(/95% confidence/)).toBeInTheDocument();
  });

  it("bridges the gap when the indicator posture disagrees with the call", () => {
    // Strong Bearish posture + BUY is the common PSX case. Unexplained, the
    // panel reads as self-contradictory.
    render(<SignalRecommendation recommendation={makeRecommendation()} setup={makeSetup()} />);
    expect(screen.getByText(/but this is about what happened/i)).toBeInTheDocument();
  });

  it("omits the bridge line when posture and call agree", () => {
    render(
      <SignalRecommendation
        recommendation={makeRecommendation()}
        setup={makeSetup({ rating: "Bullish" })}
      />,
    );
    expect(screen.queryByText(/but this is about what happened/i)).not.toBeInTheDocument();
  });

  it("explains every HOLD rather than leaving it bare", () => {
    render(
      <SignalRecommendation
        recommendation={makeRecommendation({
          rating: "HOLD",
          abstain_reason: "INTERVAL_STRADDLES_BASE_RATE",
        })}
        setup={makeSetup()}
      />,
    );
    expect(screen.getByText(/no clear edge either way/i)).toBeInTheDocument();
  });

  it("falls back to generic copy for an unrecognised abstain reason", () => {
    render(
      <SignalRecommendation
        recommendation={makeRecommendation({ rating: "HOLD", abstain_reason: "SOMETHING_NEW" })}
        setup={makeSetup()}
      />,
    );
    expect(screen.getByText(/No clear edge in the historical record/i)).toBeInTheDocument();
  });

  it("renders nothing without a recommendation", () => {
    const { container } = render(
      <SignalRecommendation recommendation={null} setup={makeSetup()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("survives a recommendation carrying no numbers", () => {
    render(
      <SignalRecommendation
        recommendation={makeRecommendation({
          rating: "HOLD",
          p: null,
          p_lower: null,
          p_upper: null,
          base_rate: null,
          round_trip_cost: null,
          suggested_stop_pct: null,
          abstain_reason: "NO_CALIBRATION_DATA",
        })}
        setup={makeSetup()}
      />,
    );
    expect(screen.getByText("Hold")).toBeInTheDocument();
    expect(screen.queryByText(/95% confidence/)).not.toBeInTheDocument();
  });

  it("discloses that buy calls face a higher bar than sell calls", () => {
    render(<SignalRecommendation recommendation={makeRecommendation()} setup={makeSetup()} />);
    expect(screen.getByText(/Buy calls require stronger evidence/i)).toBeInTheDocument();
  });

  it("shows cost and stop so the call is actionable", () => {
    render(<SignalRecommendation recommendation={makeRecommendation()} setup={makeSetup()} />);
    expect(screen.getByText("0.96%")).toBeInTheDocument();
    expect(screen.getByText("8.0%")).toBeInTheDocument();
  });
});
