import { DonutBreakdownCard, type DonutBreakdownSlice } from "@/components/charts/charts";

interface AllocSlice extends DonutBreakdownSlice {}

export function PortfolioAllocationCards({
  useDemoPortfolio,
  sectorAllocData,
  stockAllocData,
}: {
  useDemoPortfolio: boolean;
  sectorAllocData: AllocSlice[];
  stockAllocData: AllocSlice[];
}) {
  const sectorData = !useDemoPortfolio && sectorAllocData.length === 0 ? [] : sectorAllocData;
  const stockData = !useDemoPortfolio && stockAllocData.length === 0 ? [] : stockAllocData;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <DonutBreakdownCard
        title="Allocation by Sector"
        empty="No sector allocation yet. Add holdings to see your portfolio mix."
        data={sectorData}
        centerValue={`${sectorData.length} sectors`}
      />
      <DonutBreakdownCard
        title="Allocation by Stock"
        empty="No stock allocation yet. Add holdings to see your stock weights."
        data={stockData}
        centerValue={`${stockData.length} stocks`}
      />
    </div>
  );
}
