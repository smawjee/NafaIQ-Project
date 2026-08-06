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
  isLoading = false,
  intradayFallback = false,
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
  /** True while the series for the selected timeframe is still in flight. */
  isLoading?: boolean;
  /** True when an intraday timeframe fell back to daily bars. */
  intradayFallback?: boolean;
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
              tf={tf}
            />
          ) : (
            <CandlestickChart
              data={data}
              height={9999}
              mas={chartMas}
              maSeries={maSeries}
              currentPrice={price ?? undefined}
              tf={tf}
            />
          )
        ) : (
          // Distinguish "still fetching" from "genuinely nothing here". The
          // old card showed "Loading chart data..." forever for a symbol with
          // no bars at all, which reads as a hung request.
          <div className="flex h-full items-center justify-center text-sm text-text-muted">
            {isLoading ? t("Loading chart data...") : t("No price data for this range")}
          </div>
        )}
      </div>
      {intradayFallback && (
        <p className="mt-2 text-[11px] text-text-muted">
          {t("Intraday bars aren't available for this symbol yet — showing daily candles instead.")}
        </p>
      )}
      {data.length > 0 && isLive && lastBar && !intradayFallback && (
        <p className="mt-2 text-[11px] text-text-muted">
          {t("Latest candle is reconciled with today's live tick. Current close = ")}
          <span className="font-mono">{fmtNum(lastBar.close)}</span>.
        </p>
      )}
      <p className="mt-1 text-[11px] text-text-muted">{t("Drag across the chart to zoom.")}</p>
    </Card>
  );
}
