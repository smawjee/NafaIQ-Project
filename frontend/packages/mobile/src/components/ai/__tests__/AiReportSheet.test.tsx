import { fireEvent, render } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import type { ReportContent } from "@nafaiq/shared";

import { AiReportSheet } from "@/components/ai/AiReportSheet";
import { ThemeProvider } from "@/hooks/use-theme";

const report: ReportContent = {
  report_type: "market_brief",
  headline: "KSE-100 edged up",
  observations: ["Broad participation"],
  considerations: [],
  disclaimer: "Educational only.",
};

function renderSheet(ui: React.ReactElement) {
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

describe("AiReportSheet", () => {
  it("renders the trigger pill with title and subtitle", () => {
    const { getByText } = renderSheet(
      <AiReportSheet title="Market brief" subtitle="A headline" loadingLabel="Loading…" emptyLabel="Tap for insight" report={report} />,
    );
    expect(getByText("Market brief")).toBeTruthy();
    expect(getByText("A headline")).toBeTruthy();
  });

  it("falls back to the empty label when there is no subtitle", () => {
    const { getByText } = renderSheet(
      <AiReportSheet title="Market brief" loadingLabel="Loading…" emptyLabel="Tap for insight" />,
    );
    expect(getByText("Tap for insight")).toBeTruthy();
  });

  it("calls onOpen when the trigger is pressed", () => {
    const onOpen = jest.fn();
    const { getByLabelText } = renderSheet(
      <AiReportSheet title="Market brief" loadingLabel="Loading…" emptyLabel="Tap for insight" report={report} onOpen={onOpen} />,
    );
    fireEvent.press(getByLabelText("Market brief"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
