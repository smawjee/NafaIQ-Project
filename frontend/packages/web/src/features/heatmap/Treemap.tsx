import { useMemo } from "react";
import { hierarchy, treemap as d3treemap } from "d3-hierarchy";
import type { HierarchyRectangularNode } from "d3-hierarchy";
import type { ApiTreemap, ApiTreemapStock } from "@/lib/psx/types";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

type TreemapNode = {
  name: string;
  market_cap: number;
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
  children: SectorNode[];
};

const SECTOR_HEADER_HEIGHT = 18;
const MIN_TILE_W = 40;
const MIN_TILE_H = 28;

function intensity(change_pct: number): number {
  return Math.min(Math.abs(change_pct) / 4, 0.7);
}

function tileColor(change_pct: number): string {
  const base = change_pct >= 0 ? "var(--color-bull)" : "var(--color-bear)";
  const alpha = 0.18 + intensity(change_pct);
  return `color-mix(in srgb, ${base} ${Math.round(alpha * 100)}%, transparent)`;
}

function tooltipText(stock: ApiTreemapStock): string {
  const sign = stock.change_pct >= 0 ? "+" : "";
  return `${stock.symbol} â€” ${stock.name}\nPrice: ${stock.price.toFixed(
    2,
  )}  (${sign}${stock.change_pct.toFixed(2)}%)\nVolume: ${stock.volume.toLocaleString()}\nMkt Cap: ${stock.market_cap.toLocaleString()}`;
}

export function Treemap({
  data,
  height = 480,
  onStockClick,
  className,
}: {
  data: ApiTreemap;
  height?: number;
  onStockClick?: (sym: string) => void;
  className?: string;
}) {
  const { t, isUrdu } = useLang();

  if (!data || !data.sectors || data.sectors.length === 0) {
    return <div className="flex h-full items-center justify-center text-text-muted text-sm">No data</div>;
  }

  const layout = useMemo(() => {
    const root: RootNode = {
      name: "root",
      children: data.sectors.map((s) => ({
        name: s.name,
        avg_change_pct: s.avg_change_pct,
        children: s.stocks.map((st) => ({
          name: st.symbol,
          market_cap: st.market_cap,
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
    const rootHierarchy = hierarchy<any>(root).sum((d) => d.market_cap ?? 0);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const h: HierarchyRectangularNode<any> = d3treemap<any>()
      .size([width, height])
      .padding(2)
      .paddingTop(SECTOR_HEADER_HEIGHT)
      .round(true)(rootHierarchy);
    return { root: h, width };
  }, [data, height]);

  const sectors = layout.root.children ?? [];
  const totalStocks = data.stock_count;
  const sectorCount = data.sectors.length;

  return (
    <div
      className={cn("h-full w-full text-text-primary", className)}
      role="img"
      aria-label={`Sector treemap, ${sectorCount} sectors, ${totalStocks} stocks`}
    >
      <svg
        viewBox={`0 0 ${layout.width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full"
      >
        {sectors.map((sector) => {
          const sectorLabel = sector.x1 - sector.x0 < 60 ? "" : t(sector.data.name);
          const sectorLabelProps = isUrdu ? { lang: "ur" as const, dir: "rtl" as const } : {};
          // TODO (P2-d): RTL label position — fine-tune x offset for Urdu text
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
                  {sectorLabel}
                </text>
              )}
              {sector.children?.map((leaf) => {
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
                  market_cap: leaf.data.market_cap,
                  logoid: leaf.data.logoid ?? null,
                };
                return (
                  <g
                    key={leaf.data.symbol}
                    transform={`translate(${leaf.x0 - sector.x0},${leaf.y0 - sector.y0})`}
                  >
                    <rect
                      x={0}
                      y={SECTOR_HEADER_HEIGHT}
                      width={w}
                      height={h - SECTOR_HEADER_HEIGHT}
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
                    >
                      <title>{tooltipText(stock)}</title>
                    </rect>
                    {showSymbol && (
                      <text
                        x={4}
                        y={SECTOR_HEADER_HEIGHT + 12}
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
                        y={SECTOR_HEADER_HEIGHT + 24}
                        fontSize={10}
                        fill="currentColor"
                        className="pointer-events-none select-none"
                      >
                        {`${leaf.data.change_pct >= 0 ? "+" : ""}${leaf.data.change_pct.toFixed(2)}%`}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
