import { List, LayoutGrid, Flame } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { usePsxTreemap } from "@/hooks/psx/use-psx";
import { Treemap } from "@/features/heatmap/Treemap";
import { HeatmapLegend } from "@/features/heatmap/HeatmapLegend";
import { HeatmapSkeleton } from "@/features/heatmap/HeatmapSkeleton";
import { HeatmapEmptyState } from "@/features/heatmap/HeatmapEmptyState";
import { TopMoversView, type TopMover } from "@/features/heatmap/TopMoversView";

type TreemapData = NonNullable<ReturnType<typeof usePsxTreemap>["data"]>;
type HeatmapView = "treemap" | "sectors" | "movers";
type HeatmapSort = "size" | "change" | "volume";

export function PsxSectorHeatmap({
  treemapData,
  sortedTreemapData,
  isLoadingTreemap,
  heatmapView,
  onHeatmapView,
  heatmapSort,
  onHeatmapSort,
  drilledSector,
  onDrillSector,
  onDrillUp,
  renderedStockCount,
  topMovers,
  onStockNavigate,
}: {
  treemapData?: TreemapData;
  sortedTreemapData: TreemapData | null;
  isLoadingTreemap: boolean;
  heatmapView: HeatmapView;
  onHeatmapView: (view: HeatmapView) => void;
  heatmapSort: HeatmapSort;
  onHeatmapSort: (sort: HeatmapSort) => void;
  drilledSector: string | null;
  onDrillSector: (sector: string) => void;
  onDrillUp: () => void;
  renderedStockCount: number;
  topMovers: TopMover[];
  onStockNavigate: (symbol: string) => void;
}) {
  const { t } = useLang();
  return (
    <Card className="mt-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-text-primary">
            {drilledSector ? t(drilledSector) : t("Sector Heatmap")}
          </h3>
          <p className="text-[11px] text-text-muted">
            {treemapData
              ? `${treemapData.sectors.length} ${t("sectors")} · ${renderedStockCount} ${t("stocks")}`
              : t("Loading…")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Sort dropdown */}
          <select
            value={heatmapSort}
            onChange={(e) => onHeatmapSort(e.target.value as HeatmapSort)}
            className="rounded-[6px] border border-border bg-surface px-2 py-1 text-xs text-text-primary"
            disabled={!!drilledSector}
          >
            <option value="size">{t("By Size")}</option>
            <option value="change">{t("By % Change")}</option>
            <option value="volume">{t("By Volume")}</option>
          </select>
          {/* View toggle */}
          <div className="flex items-center gap-0.5 rounded-[6px] border border-border bg-surface p-0.5">
            <button
              type="button"
              onClick={() => onHeatmapView("treemap")}
              className={cn(
                "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-xs font-medium transition",
                heatmapView === "treemap"
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:bg-hover"
              )}
              title={t("Treemap view")}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onHeatmapView("sectors")}
              className={cn(
                "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-xs font-medium transition",
                heatmapView === "sectors"
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:bg-hover"
              )}
              title={t("Sectors bar list")}
            >
              <List className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onHeatmapView("movers")}
              className={cn(
                "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-xs font-medium transition",
                heatmapView === "movers"
                  ? "bg-bull text-bull-foreground"
                  : "text-text-secondary hover:bg-hover"
              )}
              title={t("Top Movers")}
            >
              <Flame className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {treemapData && <HeatmapLegend asOf={treemapData.as_of} />}

      <div className="mt-3">
        {heatmapView === "treemap" ? (
          isLoadingTreemap ? (
            <HeatmapSkeleton height={560} />
          ) : sortedTreemapData && sortedTreemapData.sectors.length > 0 ? (
            <Treemap
              data={sortedTreemapData}
              height={560}
              drilledSector={drilledSector}
              onStockClick={onStockNavigate}
              onSectorClick={onDrillSector}
              onDrillUp={onDrillUp}
            />
          ) : (
            <HeatmapEmptyState height={560} />
          )
        ) : heatmapView === "sectors" ? (
          <div className="space-y-1">
            {sortedTreemapData?.sectors.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => {
                  onHeatmapView("treemap");
                  onDrillSector(s.name);
                }}
                className="flex w-full items-center gap-2 rounded-[4px] px-2 py-1.5 text-xs hover:bg-hover"
              >
                <span className="w-40 truncate text-left font-medium text-text-primary">
                  {t(s.name)}
                </span>
                <span className="text-text-muted">· {s.stock_count}</span>
                <div className="flex-1">
                  <div className="h-4 overflow-hidden rounded bg-surface-alt">
                    <div
                      className="h-full rounded transition-all"
                      style={{
                        width: `${Math.min(Math.abs(s.avg_change_pct) * 5, 100)}%`,
                        backgroundColor:
                          (s.avg_change_pct ?? 0) >= 0
                            ? "var(--color-bull)"
                            : "var(--color-bear)",
                      }}
                    />
                  </div>
                </div>
                <Change pct={s.avg_change_pct ?? 0} />
              </button>
            ))}
          </div>
        ) : topMovers.length > 0 ? (
          <TopMoversView movers={topMovers} />
        ) : (
          <HeatmapSkeleton height={560} />
        )}
      </div>
    </Card>
  );
}
