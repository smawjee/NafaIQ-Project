import { fireEvent, render } from "@testing-library/react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import React from "react";

import { SectorHeatmap } from "@/components/psx/SectorHeatmap";
import { ThemeProvider } from "@/hooks/use-theme";
import type { ApiTreemap } from "@/hooks/queries/use-market";

const data: ApiTreemap = {
  as_of: "2026-07-21T00:00:00Z",
  stock_count: 3,
  sectors: [
    {
      name: "Finance",
      avg_change_pct: 1.2,
      total_market_cap: 1000,
      total_size_metric: 1000,
      stock_count: 2,
      stocks: [
        { symbol: "UBL", name: "United Bank", sector: "Finance", price: 100, change_pct: 2.5, volume: 50000, market_cap: 600, size_metric: 600, sizing_basis: "market_cap" },
        { symbol: "HBL", name: "Habib Bank", sector: "Finance", price: 90, change_pct: -0.8, volume: 30000, market_cap: 400, size_metric: 400, sizing_basis: "market_cap" },
      ],
    },
    {
      name: "Energy Minerals",
      avg_change_pct: -1.1,
      total_market_cap: 500,
      total_size_metric: 500,
      stock_count: 1,
      stocks: [
        { symbol: "OGDC", name: "Oil & Gas Dev", sector: "Energy Minerals", price: 120, change_pct: -1.1, volume: 90000, market_cap: 500, size_metric: 500, sizing_basis: "market_cap" },
      ],
    },
  ],
};

function renderHeatmap(ui: React.ReactElement) {
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

const noop = () => {};

describe("SectorHeatmap", () => {
  it("renders the header and sector mosaic by default", () => {
    const { getByText, getAllByText } = renderHeatmap(
      <SectorHeatmap data={data} isPending={false} isError={false} onStockPress={noop} />,
    );
    expect(getByText("Sector Heatmap")).toBeTruthy();
    expect(getAllByText("Finance").length).toBeGreaterThan(0);
  });

  it("shows a loading state while pending", () => {
    const { getByLabelText } = renderHeatmap(
      <SectorHeatmap data={undefined} isPending isError={false} onStockPress={noop} />,
    );
    expect(getByLabelText("Loading sector heatmap")).toBeTruthy();
  });

  it("shows an error state", () => {
    const { getByText } = renderHeatmap(
      <SectorHeatmap data={undefined} isPending={false} isError onStockPress={noop} />,
    );
    expect(getByText("Could not load heatmap.")).toBeTruthy();
  });

  it("reveals Top Movers only in list view and navigates on tap", () => {
    const onStockPress = jest.fn();
    const { getByLabelText, getByText, queryByText } = renderHeatmap(
      <SectorHeatmap data={data} isPending={false} isError={false} onStockPress={onStockPress} />,
    );
    // Grid view: no movers table
    expect(queryByText("Top Movers")).toBeNull();
    fireEvent.press(getByLabelText("List view"));
    expect(getByText("Top Movers")).toBeTruthy();
    // Biggest mover is UBL (+2.5%)
    fireEvent.press(getByText("UBL"));
    expect(onStockPress).toHaveBeenCalledWith("UBL");
  });

  it("opens the drill-in modal when a sector is tapped", () => {
    const { getByLabelText, getAllByLabelText } = renderHeatmap(
      <SectorHeatmap data={data} isPending={false} isError={false} onStockPress={noop} />,
    );
    // Tap the Finance sector tile (a11y label starts with the sector name)
    fireEvent.press(getAllByLabelText(/^Finance,/)[0]);
    expect(getByLabelText("Back to all sectors")).toBeTruthy();
  });
});
