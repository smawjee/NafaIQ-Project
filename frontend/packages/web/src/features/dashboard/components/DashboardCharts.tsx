import type { ComponentProps } from "react";
import {
  DonutBreakdownCard,
  PortfolioAreaChart,
  DONUT_LIGHT_PALETTE,
  type DonutBreakdownSlice,
} from "@/components/charts/charts";
import { Card } from "@/components/shared/Card";
import { cn } from "@/lib/utils";
import { useLang, localizeDigits } from "@/hooks/use-lang";
import { RANGES } from "@/features/dashboard/dashboard.data";

type Range = (typeof RANGES)[number];
type ChartData = ComponentProps<typeof PortfolioAreaChart>["data"];

interface SpendingByCat {
  categories: { category: string; pct: number; amount: number }[];
  total: number;
}
interface ShowcaseSpending {
  categories: DonutBreakdownSlice[];
  total: number;
}

export function DashboardCharts({
  range,
  onRangeChange,
  useShowcaseDashboard,
  portfolioHistoryLoading,
  portfolioChartData,
  spendingByCatLoading,
  spendingByCat,
  showcaseSpending,
}: {
  range: Range;
  onRangeChange: (range: Range) => void;
  useShowcaseDashboard: boolean;
  portfolioHistoryLoading: boolean;
  portfolioChartData: ChartData;
  spendingByCatLoading: boolean;
  spendingByCat?: SpendingByCat;
  showcaseSpending: ShowcaseSpending;
}) {
  const { t } = useLang();
  const spendingData: DonutBreakdownSlice[] =
    !useShowcaseDashboard && spendingByCat && spendingByCat.categories.length > 0
      ? spendingByCat.categories.slice(0, 5).map((c, i) => ({
          name: c.category,
          value: c.pct,
          amount: c.amount,
          color: DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length],
        }))
      : useShowcaseDashboard
        ? showcaseSpending.categories
        : [];
  const spendingTotal =
    !useShowcaseDashboard && spendingByCat ? spendingByCat.total : showcaseSpending.total;

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <Card className="lg:col-span-3">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">{t("Portfolio Value")}</h3>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => onRangeChange(r)}
                className={cn(
                  "rounded-[6px] px-2.5 py-1 text-xs font-medium transition",
                  range === r
                    ? "bg-bull text-bull-foreground"
                    : "text-text-secondary hover:bg-hover",
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        {!useShowcaseDashboard && portfolioHistoryLoading ? (
          <div className="flex h-[300px] items-center justify-center text-sm text-text-secondary">
            {t("Loading portfolio history...")}
          </div>
        ) : !useShowcaseDashboard && portfolioChartData.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
            {t("No portfolio history yet. Add holdings to build your chart.")}
          </div>
        ) : (
          <PortfolioAreaChart data={portfolioChartData} />
        )}
        <div className="mt-2 flex gap-4 text-xs text-text-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-bull" />
            {t("Portfolio")}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 bg-text-secondary" />
            {t("KSE-100")}
          </span>
        </div>
      </Card>

      <DonutBreakdownCard
        className="lg:col-span-2"
        title={t("Spending Breakdown")}
        loading={!useShowcaseDashboard && spendingByCatLoading}
        loadingLabel="Loading spending breakdown..."
        data={spendingData}
        centerValue={localizeDigits(Math.round(spendingTotal).toLocaleString())}
        centerLabel="PKR total"
        empty="No spending data yet. Add transactions to see your breakdown."
      />
    </div>
  );
}
