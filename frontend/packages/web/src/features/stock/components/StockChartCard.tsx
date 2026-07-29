import type { ComponentProps } from "react";
import { Card } from "@/components/shared/Card";
import { CandlestickChart, PriceLineChart } from "@/components/charts/charts";
import { ChartToolbar, type Indicator, type Timeframe } from "@/components/charts/ChartToolbar";
import { fmtNum, type Candle } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";

type MaSeries = ComponentProps<typeof CandlestickChart>["maSeries"];

export function StockChartCard({
  sym,
  tf,
  onTfChange,
  chartType,
  onChartTypeChange,
  chartMas,
  onChartMasChange,
  data,
  maSeries,
  price,
  isLive,
  lastBar,
}: {
  sym: string;
  tf: Timeframe;
  onTfChange: (tf: Timeframe) => void;
  chartType: "candle" | "line";
  onChartTypeChange: (type: "candle" | "line") => void;
  chartMas: Indicator[];
  onChartMasChange: (mas: Indicator[]) => void;
  data: Candle[];
  maSeries: MaSeries;
  price: number | null;
  isLive: boolean;
  lastBar?: Candle;
}) {
  const { t } = useLang();
  return (
    <Card hover={false} className="bg-surface-alt">
      {/* Phase 0 / B7: stock-detail now uses the same ChartToolbar as /psx */}
      <ChartToolbar
        sym={sym}
        nameFor={() => ""}
        onSymChange={() => {}}
        tf={tf}
        onTfChange={onTfChange}
        type={chartType}
        onTypeChange={onChartTypeChange}
        mas={chartMas}
        onMasChange={onChartMasChange}
        hideSymbolPicker
      />
      <div className="h-[300px] lg:h-[440px]">
        {data.length > 0 ? (
          chartType === "line" ? (
            <PriceLineChart
              data={data}
              height={9999}
              mas={chartMas}
              maSeries={maSeries}
              currentPrice={price ?? undefined}
            />
          ) : (
            <CandlestickChart
              data={data}
              height={9999}
              mas={chartMas}
              maSeries={maSeries}
              currentPrice={price ?? undefined}
            />
          )
        ) : (
          <div className="flex h-full items-center justify-center text-text-muted text-sm">
            {t("Loading chart data...")}
          </div>
        )}
      </div>
      {data.length > 0 && isLive && lastBar && (
        <p className="mt-2 text-[11px] text-text-muted">
          {t("Latest candle is reconciled with today's live tick. Current close = ")}
          <span className="font-mono">{fmtNum(lastBar.close)}</span>.
        </p>
      )}
    </Card>
  );
}
