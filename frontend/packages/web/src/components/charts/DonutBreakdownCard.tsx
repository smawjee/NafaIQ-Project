import { Card } from "@/components/shared/Card";
import { DonutChart } from "@/components/charts/DonutChart";
import { useLang, localizeDigits } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

export interface DonutBreakdownSlice {
  name: string;
  value: number;
  color: string;
  amount?: number;
}

export function DonutBreakdownCard({
  title,
  empty,
  data,
  centerValue,
  centerLabel,
  loading = false,
  loadingLabel,
  className,
}: {
  title: string;
  empty: string;
  data: DonutBreakdownSlice[];
  centerValue: string;
  centerLabel?: string;
  loading?: boolean;
  loadingLabel?: string;
  className?: string;
}) {
  const { t } = useLang();
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const leader = sorted[0];

  return (
    <Card className={cn("flex h-full flex-col overflow-hidden p-0", className)} hover={false}>
      <div className="border-b border-border/60 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-text-primary">{t(title)}</h3>
          {leader && !loading && (
            <span className="rounded-full border border-border bg-elevated px-2.5 py-1 text-[11px] font-medium text-text-secondary">
              {t("Top")}: {t(leader.name)} {localizeDigits(`${leader.value}%`)}
            </span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex h-[260px] items-center justify-center px-6 text-center text-sm text-text-secondary">
          {t(loadingLabel ?? "Loading...")}
        </div>
      ) : data.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center px-6 text-center text-sm text-text-secondary">
          {t(empty)}
        </div>
      ) : (
        <div className="grid flex-1 content-center gap-4 px-4 py-4 xl:grid-cols-[220px_minmax(0,1fr)] xl:items-center">
          <div className="relative mx-auto w-full max-w-[230px]">
            <div className="absolute inset-x-6 top-5 h-16 rounded-full bg-primary/10 blur-2xl" />
            <DonutChart
              data={data}
              centerValue={centerValue}
              centerLabel={centerLabel}
              showSliceLabels={false}
              showTooltip={true}
              tooltipMode="center"
              height={210}
            />
          </div>

          <div className="space-y-2.5">
            {sorted.map((slice) => (
              <div key={slice.name} className="group">
                <div className="mb-1 flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-2">
                    <span
                      className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full shadow-[0_0_12px_currentColor]"
                      style={{ background: slice.color, color: slice.color }}
                    />
                    <div className="min-w-0">
                      <span className="block truncate text-xs font-medium text-text-primary">
                        {t(slice.name)}
                      </span>
                    </div>
                  </div>
                  <span className="font-mono text-xs font-semibold tabular-nums text-text-primary">
                    {localizeDigits(`${slice.value}%`)}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-elevated">
                  <div
                    className="h-full rounded-full transition-[width] duration-300 group-hover:brightness-110"
                    style={{
                      width: `${Math.min(Math.max(slice.value, 0), 100)}%`,
                      background: slice.color,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
