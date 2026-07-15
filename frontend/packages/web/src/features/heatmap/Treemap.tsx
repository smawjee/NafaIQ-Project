import { useMemo, useState } from "react";
import { hierarchy, treemap as d3treemap } from "d3-hierarchy";
import type { HierarchyRectangularNode } from "d3-hierarchy";
import type { ApiTreemap, ApiTreemapStock } from "@/lib/psx/types";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";
import { StockTooltip } from "@/features/heatmap/StockTooltip";

type TreemapNode = {
  name: string;
  /** Real cap, or null when unknown — display only, never used for sizing. */
  market_cap: number | null;
  /** Drives tile area. May be a volume proxy; not a market cap. */
  size_metric: number;
  sizing_basis: "market_cap" | "volume_proxy";
  change_pct: number;
  symbol: string;
  fullName: string;
  price: number;
  volume: number;
  logoid?: string | null;
};

type SectorNode = {
  name: string;
  avg_change_pct: number;
  children: TreemapNode[];
};

type RootNode = {
  name: "root";
  children: SectorNode[] | TreemapNode[];
};

const SECTOR_HEADER_HEIGHT = 18;
const MIN_TILE_W = 28;
const MIN_TILE_H = 20;

function intensity(change_pct: number): number {
  return Math.min(Math.abs(change_pct) / 3, 0.6);
}

function tileColor(change_pct: number): string {
  const base = change_pct >= 0 ? "var(--color-bull)" : "var(--color-bear)";
  const alpha = 0.25 + intensity(change_pct);
  return `color-mix(in srgb, ${base} ${Math.round(alpha * 100)}%, transparent)`;
}

function tooltipText(stock: ApiTreemapStock): string {
  const sign = stock.change_pct >= 0 ? "+" : "";
  return `${stock.symbol} — ${stock.name}\nPrice: ${stock.price.toFixed(
    2,
  )}  (${sign}${stock.change_pct.toFixed(2)}%)\nVolume: ${stock.volume.toLocaleString()}\nMkt Cap: ${
    stock.market_cap != null ? stock.market_cap.toLocaleString() : "—"
  }`;
}

export function Treemap({
  data,
  height = 560,
  onStockClick,
  className,
  drilledSector,
  onSectorClick,
  onDrillUp,
}: {
  data: ApiTreemap;
  height?: number;
  onStockClick?: (sym: string) => void;
  className?: string;
  drilledSector?: string | null;
  onSectorClick?: (sectorName: string) => void;
  onDrillUp?: () => void;
}) {
  const { t, isUrdu } = useLang();
  const [tooltipState, setTooltipState] = useState<{
    stock: ApiTreemapStock | null;
    x: number;
    y: number;
  }>({ stock: null, x: 0, y: 0 });

  const hasData = Boolean(data && data.sectors && data.sectors.length > 0);

  const layout = useMemo(() => {
    // Hooks must run unconditionally — the empty-data guard lives below this
    // memo, so bail out here rather than before it.
    if (!hasData) {
      return { root: null, width: 1000, sectorName: null };
    }
    if (drilledSector) {
      // Single-sector view: render that sector's stocks as a flat treemap
      const sector = data.sectors.find((s) => s.name === drilledSector);
      if (!sector) {
        return { root: null as any, width: 1000, sectorName: null };
      }
      const root: RootNode = {
        name: "root",
        children: sector.stocks.map((st) => ({
          name: st.symbol,
          market_cap: st.market_cap,
          size_metric: st.size_metric,
          sizing_basis: st.sizing_basis,
          change_pct: st.change_pct,
          symbol: st.symbol,
          fullName: st.name,
          price: st.price,
          volume: st.volume,
          logoid: st.logoid,
        })),
      };
      const width = 1000;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const rootHierarchy = hierarchy<any>(root).sum((d) => d.size_metric ?? 0);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const h: HierarchyRectangularNode<any> = d3treemap<any>()
        .size([width, height])
        .padding(2)
        .round(true)(rootHierarchy);
      return { root: h, width, sectorName: sector.name };
    }

    // Default: full sector tree
    const root: RootNode = {
      name: "root",
      children: data.sectors.map((s) => ({
        name: s.name,
        avg_change_pct: s.avg_change_pct,
        children: s.stocks.map((st) => ({
          name: st.symbol,
          market_cap: st.market_cap,
          size_metric: st.size_metric,
          sizing_basis: st.sizing_basis,
          change_pct: st.change_pct,
          symbol: st.symbol,
          fullName: st.name,
          price: st.price,
          volume: st.volume,
          logoid: st.logoid,
        })),
      })),
    };
    const width = 1000;
    // d3-hierarchy's recursive layout requires a single `any` pivot at the
    // top of the tree (its typings don't model nested children), then the
    // returned node is a fully-laid-out HierarchyRectangularNode.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rootHierarchy = hierarchy<any>(root).sum((d) => d.size_metric ?? 0);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const h: HierarchyRectangularNode<any> = d3treemap<any>()
      .size([width, height])
      .padding(2)
      .paddingTop(SECTOR_HEADER_HEIGHT)
      .round(true)(rootHierarchy);
    return { root: h, width, sectorName: null };
  }, [data, height, drilledSector, hasData]);

  if (!hasData) {
    return <div className="flex h-full items-center justify-center text-text-muted text-sm">No data</div>;
  }

  const sectors = layout.root?.children ?? [];
  // Per-sector counts are post-cap; the payload's top-level stock_count is not.
  // Summing keeps the label honest about how many tiles are actually drawn.
  const totalStocks = data.sectors.reduce((n, s) => n + s.stock_count, 0);
  const sectorCount = data.sectors.length;

  const renderLeaf = (
    leaf: HierarchyRectangularNode<any>,
    offsetX: number,
    offsetY: number,
    keyPrefix: string,
  ) => {
    const w = leaf.x1 - leaf.x0;
    const h = leaf.y1 - leaf.y0;
    if (w < MIN_TILE_W || h < MIN_TILE_H) return null;
    const showPct = h >= 36;
    const showSymbol = w >= 32;
    const stock: ApiTreemapStock = {
      symbol: leaf.data.symbol,
      name: leaf.data.fullName,
      price: leaf.data.price,
      change_pct: leaf.data.change_pct,
      volume: leaf.data.volume,
      market_cap: leaf.data.market_cap ?? null,
      size_metric: leaf.data.size_metric,
      sizing_basis: leaf.data.sizing_basis,
      logoid: leaf.data.logoid ?? null,
    };
    // No header offset here: d3's .paddingTop() already insets a sector's
    // children, so `offsetY` (leaf.y0 - sector.y0) clears the label band.
    return (
      <g
        key={`${keyPrefix}-${leaf.data.symbol}`}
        transform={`translate(${offsetX},${offsetY})`}
      >
        <rect
          x={0}
          y={0}
          width={w}
          height={h}
          fill={tileColor(leaf.data.change_pct)}
          stroke="var(--color-border)"
          strokeWidth={0.5}
          rx={2}
          className="cursor-pointer transition-opacity hover:opacity-80"
          onClick={() => onStockClick?.(leaf.data.symbol)}
          tabIndex={0}
          role="button"
          aria-label={`${leaf.data.symbol} - ${leaf.data.change_pct >= 0 ? "+" : ""}${leaf.data.change_pct.toFixed(2)}%`}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onStockClick?.(leaf.data.symbol);
            }
          }}
          onMouseMove={(e) => {
            setTooltipState({ stock, x: e.clientX, y: e.clientY });
          }}
          onMouseLeave={() => {
            setTooltipState({ stock: null, x: 0, y: 0 });
          }}
        >
          <title>{tooltipText(stock)}</title>
        </rect>
        {showSymbol && (
          <text
            x={4}
            y={12}
            fontSize={11}
            fontWeight={600}
            fill="currentColor"
            className="pointer-events-none select-none"
          >
            {leaf.data.symbol}
          </text>
        )}
        {showPct && (
          <text
            x={4}
            y={24}
            fontSize={10}
            fill="currentColor"
            className="pointer-events-none select-none"
          >
            {`${leaf.data.change_pct >= 0 ? "+" : ""}${leaf.data.change_pct.toFixed(2)}%`}
          </text>
        )}
      </g>
    );
  };

  return (
    <div
      className={cn("relative h-full w-full text-text-primary", className)}
      role="img"
      aria-label={`Sector treemap, ${sectorCount} sectors, ${totalStocks} stocks`}
    >
      {drilledSector && onDrillUp && (
        <div className="absolute left-3 top-3 z-10">
          <button
            type="button"
            onClick={onDrillUp}
            className="inline-flex items-center gap-1 rounded-[6px] border border-border bg-surface px-2.5 py-1 text-xs font-medium text-text-secondary transition hover:bg-hover"
          >
            ← {t("All sectors")}
          </button>
        </div>
      )}

      {drilledSector && (
        <div className="absolute right-3 top-3 z-10 rounded-[6px] border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text-primary">
          {t(drilledSector)}
        </div>
      )}

      <svg
        viewBox={`0 0 ${layout.width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full"
      >
        {sectors.map((sector: HierarchyRectangularNode<any>) => {
          if (drilledSector) {
            return renderLeaf(sector, sector.x0, sector.y0, "drilled");
          }

          const sectorLabel = sector.x1 - sector.x0 < 60 ? "" : t(sector.data.name);
          const sectorLabelProps = isUrdu ? { lang: "ur" as const, dir: "rtl" as const } : {};
          // TODO (P2-d): RTL label position – fine-tune x offset for Urdu text
          return (
            <g key={sector.data.name} transform={`translate(${sector.x0},${sector.y0})`}>
              <rect
                x={0}
                y={0}
                width={sector.x1 - sector.x0}
                height={sector.y1 - sector.y0}
                fill="var(--color-surface)"
                stroke="var(--color-border)"
                strokeWidth={1}
                rx={2}
                className={onSectorClick ? "cursor-pointer transition-opacity hover:opacity-80" : ""}
                onClick={() => onSectorClick?.(sector.data.name)}
                role={onSectorClick ? "button" : undefined}
                tabIndex={onSectorClick ? 0 : undefined}
                aria-label={onSectorClick ? `Drill into ${sector.data.name}` : undefined}
                onKeyDown={(e) => {
                  if (onSectorClick && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    onSectorClick(sector.data.name);
                  }
                }}
              />
              {sectorLabel && (
                <text
                  {...sectorLabelProps}
                  x={isUrdu ? sector.x1 - sector.x0 - 4 : 4}
                  y={13}
                  textAnchor={isUrdu ? "end" : "start"}
                  fontSize={11}
                  fontWeight={600}
                  fill="currentColor"
                  className="select-none"
                >
                  {sectorLabel}{" "}
                  <tspan fontSize={9} fill="var(--color-text-muted)">
                    · {sector.data.children?.length ?? 0}
                  </tspan>
                </text>
              )}
              {sector.children?.map((leaf: HierarchyRectangularNode<any>) =>
                renderLeaf(leaf, leaf.x0 - sector.x0, leaf.y0 - sector.y0, sector.data.name),
              )}
            </g>
          );
        })}
      </svg>

      <StockTooltip
        stock={tooltipState.stock}
        x={tooltipState.x}
        y={tooltipState.y}
        visible={!!tooltipState.stock}
      />
    </div>
  );
}
