import type { ComponentProps } from "react";
import { Card } from "@/components/shared/Card";
import { PortfolioAreaChart } from "@/components/charts/charts";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { RANGES } from "@/features/portfolio/portfolio.data";

type Range = (typeof RANGES)[number];
type PerformanceData = ComponentProps<typeof PortfolioAreaChart>["data"];

export function PortfolioPerformanceCard({
  range,
  onRangeChange,
  benchmarkDiff,
  shouldUseUserPerformance,
  performanceData,
  portfolioHistoryLoading,
}: {
  range: Range;
  onRangeChange: (range: Range) => void;
  benchmarkDiff: number | null;
  shouldUseUserPerformance: boolean;
  performanceData: PerformanceData;
  portfolioHistoryLoading: boolean;
}) {
  const { t } = useLang();
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{t("Performance vs KSE-100")}</h3>
          <span
            className={cn(
              "text-xs",
              benchmarkDiff == null
                ? "text-text-muted"
                : benchmarkDiff >= 0
                  ? "text-bull"
                  : "text-bear",
            )}
          >
            {shouldUseUserPerformance
              ? benchmarkDiff == null
                ? t("Add holdings to compare performance with KSE-100")
                : `${benchmarkDiff >= 0 ? t("Outperforming") : t("Underperforming")} ${t("benchmark by")} ${benchmarkDiff >= 0 ? "+" : ""}${benchmarkDiff.toFixed(2)}%`
              : t("Outperforming benchmark by +3.2%")}
          </span>
        </div>
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => onRangeChange(r)}
              className={cn(
                "rounded-[6px] px-2.5 py-1 text-xs font-medium",
                range === r ? "bg-bull text-bull-foreground" : "text-text-secondary hover:bg-hover",
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
      {shouldUseUserPerformance && portfolioHistoryLoading ? (
        <div className="flex h-[280px] items-center justify-center text-sm text-text-secondary">
          {t("Loading portfolio history...")}
        </div>
      ) : shouldUseUserPerformance && performanceData.length === 0 ? (
        <div className="flex h-[280px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
          {t("No portfolio history yet. Add holdings to build your performance chart.")}
        </div>
      ) : (
        <PortfolioAreaChart data={performanceData} height={280} />
      )}
    </Card>
  );
}
