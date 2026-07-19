import { Card } from "@/components/shared/Card";
import { DonutChart } from "@/components/charts/charts";
import { useLang } from "@/hooks/use-lang";

interface AllocSlice {
  name: string;
  value: number;
  color: string;
}

export function PortfolioAllocationCards({
  useDemoPortfolio,
  sectorAllocData,
  stockAllocData,
}: {
  useDemoPortfolio: boolean;
  sectorAllocData: AllocSlice[];
  stockAllocData: AllocSlice[];
}) {
  const { t } = useLang();
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <h3 className="mb-2 text-sm font-semibold text-text-primary">
          {t("Allocation by Sector")}
        </h3>
        {!useDemoPortfolio && sectorAllocData.length === 0 ? (
          <div className="flex h-[220px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
            {t("No sector allocation yet. Add holdings to see your portfolio mix.")}
          </div>
        ) : (
          <>
            <DonutChart
              data={sectorAllocData}
              centerValue={`${sectorAllocData.length} sectors`}
            />
            <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
              {sectorAllocData.map((s) => (
                <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                  <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                  {t(s.name)} {s.value}%
                </span>
              ))}
            </div>
          </>
        )}
      </Card>
      <Card>
        <h3 className="mb-2 text-sm font-semibold text-text-primary">
          {t("Allocation by Stock")}
        </h3>
        {!useDemoPortfolio && stockAllocData.length === 0 ? (
          <div className="flex h-[220px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
            {t("No stock allocation yet. Add holdings to see your stock weights.")}
          </div>
        ) : (
          <>
            <DonutChart data={stockAllocData} centerValue={`${stockAllocData.length} stocks`} />
            <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
              {stockAllocData.map((s) => (
                <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                  <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                  {t(s.name)} {s.value}%
                </span>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
