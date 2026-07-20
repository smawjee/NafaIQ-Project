import { fireEvent, render } from "@testing-library/react-native";
import type { ReportContent } from "@nafaiq/shared";

import { AiReportView } from "@/components/ai/AiReportView";
import { ThemeProvider } from "@/hooks/use-theme";

const report: ReportContent = {
  report_type: "market_brief",
  headline: "KSE-100 slipped as banks dragged a narrow tape",
  observations: ["Advancers trailed decliners", "Banks led the decline"],
  considerations: [
    {
      consideration: "Concentrated exposure carries more risk",
      hedge: "Historically, diversification is one approach investors consider.",
    },
  ],
  disclaimer: "Educational information only. Not financial advice.",
  citations: [{ value: "181,259.67", source_key: "indices.kse100.close", as_of: "2026-07-20" }],
};

function renderView(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("AiReportView", () => {
  it("renders headline, observations, considerations and disclaimer", () => {
    const { getByText } = renderView(<AiReportView report={report} />);
    expect(getByText(report.headline)).toBeTruthy();
    expect(getByText("Banks led the decline")).toBeTruthy();
    expect(getByText(report.considerations[0].consideration)).toBeTruthy();
    expect(getByText(report.disclaimer)).toBeTruthy();
  });

  it("hides citation source keys until 'View sources' is tapped", () => {
    const { queryByText, getByText, getByLabelText } = renderView(<AiReportView report={report} />);
    expect(queryByText(/indices\.kse100\.close/)).toBeNull();
    fireEvent.press(getByLabelText("View sources"));
    expect(getByText(/indices\.kse100\.close/)).toBeTruthy();
  });

  it("nudge variant drops the sources toggle but keeps the disclaimer", () => {
    const { queryByLabelText, getByText } = renderView(<AiReportView report={report} variant="nudge" />);
    expect(queryByLabelText("View sources")).toBeNull();
    expect(getByText(report.disclaimer)).toBeTruthy();
  });
});
