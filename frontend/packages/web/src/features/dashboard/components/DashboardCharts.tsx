import type { ComponentProps } from "react";
import { Card } from "@/components/shared/Card";
import { DonutChart, PortfolioAreaChart, DONUT_LIGHT_PALETTE } from "@/components/charts/charts";
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
  categories: { name: string; value: number; color: string }[];
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
  theme,
}: {
  range: Range;
  onRangeChange: (range: Range) => void;
  useShowcaseDashboard: boolean;
  portfolioHistoryLoading: boolean;
  portfolioChartData: ChartData;
  spendingByCatLoading: boolean;
  spendingByCat?: SpendingByCat;
  showcaseSpending: ShowcaseSpending;
  theme: string;
}) {
  const { t } = useLang();
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
      <Card className="lg:col-span-2">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Spending Breakdown")}</h3>
        {!useShowcaseDashboard && spendingByCatLoading ? (
          <div className="flex h-[220px] items-center justify-center text-sm text-text-secondary">
            {t("Loading spending breakdown...")}
          </div>
        ) : !useShowcaseDashboard && spendingByCat && spendingByCat.categories.length > 0 ? (
          <>
            <DonutChart
              data={spendingByCat.categories.slice(0, 5).map((c, i) => ({
                name: c.category,
                value: c.pct,
                amount: c.amount,
                color: DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length],
              }))}
              centerValue={localizeDigits(Math.round(spendingByCat.total).toLocaleString())}
              centerLabel="PKR total"
            />
            <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
              {spendingByCat.categories.slice(0, 5).map((c, i) => (
                <span key={c.category} className="flex items-center gap-1.5 text-text-secondary">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length] }}
                  />
                  {t(c.category)} {localizeDigits(`${c.pct}%`)}
                </span>
              ))}
            </div>
          </>
        ) : !useShowcaseDashboard ? (
          <div className="flex h-[220px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
            {t("No spending data yet. Add transactions to see your breakdown.")}
          </div>
        ) : (
          <>
            <DonutChart
              data={showcaseSpending.categories}
              centerValue={localizeDigits(Math.round(showcaseSpending.total).toLocaleString())}
              centerLabel="PKR total"
            />
            <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
              {showcaseSpending.categories.map((s, i) => (
                <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{
                      background:
                        theme === "light"
                          ? DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length]
                          : s.color,
                    }}
                  />
                  {t(s.name)} {localizeDigits(`${s.value}%`)}
                </span>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
