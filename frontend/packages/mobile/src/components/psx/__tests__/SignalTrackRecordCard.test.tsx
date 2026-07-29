/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { render } from "@testing-library/react-native";
import React from "react";

jest.mock("@/hooks/queries/use-market", () => ({
  usePsxSignalTrackRecord: jest.fn(),
}));

import { SignalTrackRecordCard } from "@/components/psx/SignalTrackRecordCard";
import { usePsxSignalTrackRecord } from "@/hooks/queries/use-market";
import { ThemeProvider } from "@/hooks/use-theme";

const mUseTrackRecord = usePsxSignalTrackRecord as jest.Mock;

function renderCard() {
  return render(
    <ThemeProvider>
      <SignalTrackRecordCard />
    </ThemeProvider>,
  );
}

beforeEach(() => jest.clearAllMocks());

describe("SignalTrackRecordCard", () => {
  it("renders nothing while loading or without data", () => {
    mUseTrackRecord.mockReturnValue({ data: undefined, isLoading: true });
    expect(renderCard().toJSON()).toBeNull();

    mUseTrackRecord.mockReturnValue({ data: undefined, isLoading: false });
    expect(renderCard().toJSON()).toBeNull();
  });

  it("shows the recording note before any outcomes mature", () => {
    mUseTrackRecord.mockReturnValue({
      isLoading: false,
      data: { matured_total: 0, by_signal: {}, pending_maturity: 42, note: "" },
    });
    const { getByText } = renderCard();
    expect(getByText("Signal Track Record")).toBeTruthy();
    expect(getByText("0 matured · 42 pending")).toBeTruthy();
    expect(getByText(/Signals are being recorded daily/)).toBeTruthy();
  });

  it("renders matured rows with hit rates, and avoided-loss framing for sells", () => {
    mUseTrackRecord.mockReturnValue({
      isLoading: false,
      data: {
        matured_total: 31,
        pending_maturity: 12,
        note: "",
        by_signal: {
          STRONG_BUY: { n: 9, hit_rate: 0.62, avg_return: 0.05, avg_excess: 0.031, large_loss_rate: 0.1 },
          SELL: {
            n: 6,
            hit_rate: 0.2,
            avg_return: -0.01,
            avg_excess: -0.012,
            large_loss_rate: 0.05,
            avoided_loss_rate: 0.7,
          },
        },
      },
    });
    const { getByText } = renderCard();

    expect(getByText("STRONG BUY")).toBeTruthy();
    expect(getByText("62%")).toBeTruthy(); // hit rate headline for buys
    expect(getByText("3.1%")).toBeTruthy(); // avg excess vs KSE-100
    expect(getByText("SELL")).toBeTruthy();
    expect(getByText("(fall avoided)")).toBeTruthy();
    expect(getByText("70%")).toBeTruthy(); // avoided-loss headline, not hit_rate
    expect(getByText("31 matured · 12 pending")).toBeTruthy();
  });
});
