// Render smoke tests for the new pushed routes. expo-router + each screen's
// data hook are mocked so the screens render their data/empty states on a
// virtual device.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { render } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import React from "react";

jest.mock("expo-router", () => ({
  Stack: { Screen: () => null },
  useRouter: () => ({ push: jest.fn(), back: jest.fn() }),
}));

jest.mock("@/hooks/queries/use-news", () => ({ useLatestNews: jest.fn() }));
jest.mock("@/hooks/queries/use-funds", () => ({ useFunds: jest.fn() }));
jest.mock("@/hooks/queries/use-dividends", () => ({ useDividends: jest.fn() }));
jest.mock("@/hooks/queries/use-macro", () => ({
  useMacroFx: jest.fn(),
  useMacroRates: jest.fn(),
  usePolicyRate: jest.fn(),
}));

import { ThemeProvider } from "@/hooks/use-theme";
import { useLatestNews } from "@/hooks/queries/use-news";
import { useFunds } from "@/hooks/queries/use-funds";
import { useDividends } from "@/hooks/queries/use-dividends";
import { useMacroFx, useMacroRates, usePolicyRate } from "@/hooks/queries/use-macro";
import NewsScreen from "@/app/news";
import FundsScreen from "@/app/funds";
import DividendsScreen from "@/app/dividends";
import MoreScreen from "@/app/more";

const idle = { isPending: false, isError: false, refetch: jest.fn() };

function renderScreen(ui: React.ReactElement) {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 0, left: 0, right: 0, bottom: 0 },
      }}
    >
      <ThemeProvider>{ui}</ThemeProvider>
    </SafeAreaProvider>,
  );
}

beforeEach(() => jest.clearAllMocks());

describe("NewsScreen", () => {
  it("renders a news headline from the hook", () => {
    (useLatestNews as jest.Mock).mockReturnValue({
      ...idle,
      data: [{ id: 1, headline: "KSE-100 rallies", url: "https://x.co", source: "PSX", published_at: null, tickers: [] }],
    });
    const { getByText } = renderScreen(<NewsScreen />);
    expect(getByText("KSE-100 rallies")).toBeTruthy();
  });
});

describe("FundsScreen", () => {
  it("renders a fund name from the hook", () => {
    (useFunds as jest.Mock).mockReturnValue({
      ...idle,
      data: [{ fund_code: "MMF01", name: "Meezan Money Market", category: "Money Market", nav: 51.2 }],
    });
    const { getByText } = renderScreen(<FundsScreen />);
    expect(getByText("Meezan Money Market")).toBeTruthy();
  });
});

describe("DividendsScreen", () => {
  it("renders a dividend symbol from the hook", () => {
    (useDividends as jest.Mock).mockReturnValue({
      ...idle,
      data: [{ announcement_id: "a1", symbol: "HBL", payout_type: "Cash", per_share: 7, bonus_pct: null, ex_date: "2026-06-01", announcement_date: "2026-05-01" }],
    });
    const { getByText } = renderScreen(<DividendsScreen />);
    expect(getByText("HBL")).toBeTruthy();
  });
});

describe("MoreScreen", () => {
  it("renders the hub navigation rows", () => {
    (usePolicyRate as jest.Mock).mockReturnValue({ ...idle, data: { date: "2026-06-01", rate: 22 } });
    (useMacroFx as jest.Mock).mockReturnValue({ ...idle, data: [] });
    (useMacroRates as jest.Mock).mockReturnValue({ ...idle, data: [] });
    const { getByText } = renderScreen(<MoreScreen />);
    expect(getByText("Market News")).toBeTruthy();
    expect(getByText("Mutual Funds")).toBeTruthy();
    expect(getByText("Dividends")).toBeTruthy();
  });
});
