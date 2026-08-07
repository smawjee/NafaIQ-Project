import { useId, useMemo, useState } from "react";
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
  sector: string;
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

type LayoutDatum = RootNode | SectorNode | TreemapNode;

const SECTOR_HEADER_HEIGHT = 32;
const MIN_TILE_W = 36;
const MIN_TILE_H = 26;
const TREEMAP_WIDTH = 1280;

function isTreemapNode(node: LayoutDatum): node is TreemapNode {
  return "symbol" in node;
}

function isSectorNode(node: LayoutDatum): node is SectorNode {
  return "avg_change_pct" in node;
}

function intensity(change_pct: number): number {
  return Math.min(Math.abs(change_pct) / 3, 0.62);
}

function tileColor(change_pct: number): string {
  if (Math.abs(change_pct) <= 0.1) {
    return "color-mix(in srgb, var(--color-elevated) 88%, var(--color-text-muted))";
  }
  const base = change_pct >= 0 ? "var(--color-bull)" : "var(--color-bear)";
  const weight = 24 + intensity(change_pct) * 78;
  return `color-mix(in srgb, ${base} ${Math.round(weight)}%, var(--color-elevated))`;
}

function sectorAbbr(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 4)
    .toUpperCase();
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
  width = TREEMAP_WIDTH,
  onStockClick,
  className,
  drilledSector,
  highlightedSector,
  onSectorClick,
  onSectorDoubleClick,
  onDrillUp,
}: {
  data: ApiTreemap;
  height?: number;
  width?: number;
  onStockClick?: (sym: string) => void;
  className?: string;
  drilledSector?: string | null;
  highlightedSector?: string | null;
  onSectorClick?: (sectorName: string) => void;
  onSectorDoubleClick?: (sectorName: string) => void;
  onDrillUp?: () => void;
}) {
  const { t, isUrdu } = useLang();
  const clipIdBase = useId().replace(/:/g, "");
  const sectorHeaderGradientId = `${clipIdBase}-sector-header-gradient`;
  const sectorHeaderActiveGradientId = `${clipIdBase}-sector-header-active-gradient`;
  const [hoveredSector, setHoveredSector] = useState<string | null>(null);
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
      return { root: null, width, sectorName: null };
    }
    if (drilledSector) {
      // Single-sector view: render that sector's stocks as a flat treemap
      const sector = data.sectors.find((s) => s.name === drilledSector);
      if (!sector) {
        return { root: null, width: TREEMAP_WIDTH, sectorName: null };
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
          sector: sector.name,
          logoid: st.logoid,
        })),
      };
      const rootHierarchy = hierarchy<LayoutDatum>(root).sum((d) =>
        isTreemapNode(d) ? d.size_metric : 0,
      );
      const h: HierarchyRectangularNode<LayoutDatum> = d3treemap<LayoutDatum>()
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
          sector: s.name,
          logoid: st.logoid,
        })),
      })),
    };
    const rootHierarchy = hierarchy<LayoutDatum>(root).sum((d) =>
      isTreemapNode(d) ? d.size_metric : 0,
    );
    const h: HierarchyRectangularNode<LayoutDatum> = d3treemap<LayoutDatum>()
      .size([width, height])
      .paddingOuter(0)
      .paddingInner((node) => (node.depth === 0 ? 8 : 2))
      .paddingTop((node) => (isSectorNode(node.data) ? SECTOR_HEADER_HEIGHT : 0))
      .round(true)(rootHierarchy);
    return { root: h, width, sectorName: null };
  }, [data, height, width, drilledSector, hasData]);

  if (!hasData) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        {t("No data")}
      </div>
    );
  }

  const sectors = layout.root?.children ?? [];
  // Per-sector counts are post-cap; the payload's top-level stock_count is not.
  // Summing keeps the label honest about how many tiles are actually drawn.
  const totalStocks = data.sectors.reduce((n, s) => n + s.stock_count, 0);
  const sectorCount = data.sectors.length;

  const renderLeaf = (
    leaf: HierarchyRectangularNode<LayoutDatum>,
    offsetX: number,
    offsetY: number,
    keyPrefix: string,
  ) => {
    const stockNode = leaf.data;
    if (!isTreemapNode(stockNode)) return null;
    const w = leaf.x1 - leaf.x0;
    const h = leaf.y1 - leaf.y0;
    if (w < MIN_TILE_W || h < MIN_TILE_H) return null;
    const showPct = h >= 38 && w >= 42;
    const showSymbol = w >= 42;
    const stock: ApiTreemapStock = {
      symbol: stockNode.symbol,
      name: stockNode.fullName,
      price: stockNode.price,
      change_pct: stockNode.change_pct,
      volume: stockNode.volume,
      sector: stockNode.sector,
      market_cap: stockNode.market_cap ?? null,
      size_metric: stockNode.size_metric,
      sizing_basis: stockNode.sizing_basis,
      logoid: stockNode.logoid ?? null,
    };
    // No header offset here: d3's .paddingTop() already insets a sector's
    // children, so `offsetY` (leaf.y0 - sector.y0) clears the label band.
    return (
      <g key={`${keyPrefix}-${stockNode.symbol}`} transform={`translate(${offsetX},${offsetY})`}>
        <rect
          x={0}
          y={0}
          width={w}
          height={h}
          fill={tileColor(stockNode.change_pct)}
          stroke="color-mix(in srgb, var(--color-border) 78%, transparent)"
          strokeWidth={0.75}
          rx={3}
          className="cursor-pointer transition-opacity hover:opacity-90"
          onClick={() => onStockClick?.(stockNode.symbol)}
          tabIndex={0}
          role="button"
          aria-label={`${stockNode.symbol} - ${stockNode.change_pct >= 0 ? "+" : ""}${stockNode.change_pct.toFixed(2)}%`}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onStockClick?.(stockNode.symbol);
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
            x={5}
            y={13}
            fontSize={11}
            fontWeight={700}
            fill="currentColor"
            className="heatmap-tile-label pointer-events-none select-none"
            style={{ textShadow: "0 1px 2px rgba(0,0,0,0.28)" }}
          >
            {stockNode.symbol}
          </text>
        )}
        {showPct && (
          <text
            x={5}
            y={25}
            fontSize={10}
            fill="currentColor"
            className="heatmap-tile-label pointer-events-none select-none"
            style={{ textShadow: "0 1px 2px rgba(0,0,0,0.28)" }}
          >
            {`${stockNode.change_pct >= 0 ? "+" : ""}${stockNode.change_pct.toFixed(2)}%`}
          </text>
        )}
      </g>
    );
  };

  return (
    <div
      className={cn("relative h-full w-full text-text-primary", className)}
      style={{ height }}
      role="img"
      aria-label={`Sector treemap, ${sectorCount} sectors, ${totalStocks} stocks`}
    >
      {drilledSector && onDrillUp && (
        <div className="absolute start-3 top-3 z-10">
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
        <div className="absolute end-3 top-3 z-10 rounded-[6px] border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text-primary">
          {t(drilledSector)}
        </div>
      )}

      <svg
        viewBox={`0 0 ${layout.width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        className="h-full w-full rounded-[8px]"
      >
        <defs>
          <linearGradient id={sectorHeaderGradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="color-mix(in srgb, var(--color-surface-alt) 88%, white)" />
            <stop offset="100%" stopColor="color-mix(in srgb, var(--color-elevated) 92%, black)" />
          </linearGradient>
          <linearGradient id={sectorHeaderActiveGradientId} x1="0" y1="0" x2="1" y2="1">
            <stop
              offset="0%"
              stopColor="color-mix(in srgb, var(--color-bull) 16%, var(--color-surface-alt))"
            />
            <stop offset="100%" stopColor="color-mix(in srgb, var(--color-elevated) 88%, black)" />
          </linearGradient>
        </defs>
        {sectors.map((sector: HierarchyRectangularNode<LayoutDatum>) => {
          if (drilledSector) {
            return renderLeaf(sector, sector.x0, sector.y0, "drilled");
          }

          if (!isSectorNode(sector.data)) return null;

          const sectorW = sector.x1 - sector.x0;
          const sectorH = sector.y1 - sector.y0;
          const sectorName = t(sector.data.name);
          const showIcon = sectorW >= 220;
          const showCount = sectorW >= 120;
          const compactLabel = sectorW < 92 ? sectorAbbr(sectorName) : sectorName;
          const headerHeight = Math.min(SECTOR_HEADER_HEIGHT, Math.max(20, sectorH));
          const headerClipId = `${clipIdBase}-${sector.data.name.replace(/[^a-z0-9]/gi, "-")}`;
          const activeSector = (highlightedSector ?? hoveredSector) === sector.data.name;
          const dimmedSector = Boolean(highlightedSector ?? hoveredSector) && !activeSector;
          const labelStart = showIcon ? 28 : 12;
          const labelWidth = Math.max(22, sectorW - labelStart - (showCount ? 46 : 10));
          const sectorLabelProps = isUrdu ? { lang: "ur" as const, dir: "rtl" as const } : {};
          // TODO (P2-d): RTL label position – fine-tune x offset for Urdu text
          return (
            <g
              key={sector.data.name}
              transform={`translate(${sector.x0},${sector.y0})`}
              opacity={dimmedSector ? 0.42 : 1}
              className="transition-opacity duration-200"
              onMouseEnter={() => setHoveredSector(sector.data.name)}
              onMouseLeave={() => setHoveredSector(null)}
            >
              <title>
                {sectorName} - {sector.data.children?.length ?? 0} {t("stocks")}
              </title>
              <clipPath id={headerClipId}>
                <rect x={labelStart} y={4} width={labelWidth} height={headerHeight - 8} />
              </clipPath>
              <rect
                x={0}
                y={0}
                width={sectorW}
                height={sectorH}
                fill="var(--color-elevated)"
                stroke={
                  activeSector
                    ? "color-mix(in srgb, var(--color-bull) 58%, var(--color-border))"
                    : "color-mix(in srgb, var(--color-border) 88%, transparent)"
                }
                strokeWidth={activeSector ? 1.5 : 1}
                rx={5}
                className={
                  onSectorClick ? "cursor-pointer transition-[stroke,opacity] duration-200" : ""
                }
                onClick={() => onSectorClick?.(sector.data.name)}
                onDoubleClick={() => onSectorDoubleClick?.(sector.data.name)}
                role={onSectorClick ? "button" : undefined}
                tabIndex={onSectorClick ? 0 : undefined}
                aria-label={onSectorClick ? `Drill into ${sector.data.name}` : undefined}
                onKeyDown={(e) => {
                  if (onSectorClick && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onSectorClick(sector.data.name);
                  }
                }}
              />
              <rect
                x={1}
                y={1}
                width={Math.max(0, sectorW - 2)}
                height={Math.max(0, headerHeight - 1)}
                fill={
                  activeSector
                    ? `url(#${sectorHeaderActiveGradientId})`
                    : `url(#${sectorHeaderGradientId})`
                }
                stroke="color-mix(in srgb, var(--color-border) 70%, transparent)"
                strokeWidth={1}
                rx={4}
                className={onSectorClick ? "cursor-pointer" : ""}
                onClick={() => onSectorClick?.(sector.data.name)}
                onDoubleClick={() => onSectorDoubleClick?.(sector.data.name)}
              />
              <rect
                x={1}
                y={1}
                width={3}
                height={Math.max(0, headerHeight - 2)}
                fill="var(--color-bull)"
                rx={2}
              />
              <line
                x1={4}
                y1={headerHeight}
                x2={Math.max(4, sectorW - 2)}
                y2={headerHeight}
                stroke="color-mix(in srgb, var(--color-bull) 32%, var(--color-border))"
                strokeWidth={1}
              />
              {showIcon && (
                <circle
                  cx={17}
                  cy={headerHeight / 2}
                  r={5}
                  fill="color-mix(in srgb, var(--color-bull) 26%, transparent)"
                  stroke="color-mix(in srgb, var(--color-bull) 52%, transparent)"
                  strokeWidth={1}
                />
              )}
              {sectorW >= 48 && (
                <text
                  {...sectorLabelProps}
                  x={isUrdu ? sectorW - (showCount ? 46 : 8) : labelStart}
                  y={headerHeight / 2 + 4}
                  textAnchor={isUrdu ? "end" : "start"}
                  fontSize={sectorW < 92 ? 11 : 12}
                  fontWeight={800}
                  letterSpacing={0.35}
                  fill="color-mix(in srgb, var(--color-text-primary) 90%, white)"
                  clipPath={`url(#${headerClipId})`}
                  className="pointer-events-none select-none"
                >
                  {compactLabel}
                </text>
              )}
              {showCount && (
                <>
                  <rect
                    x={sectorW - 34}
                    y={6}
                    width={26}
                    height={headerHeight - 12}
                    rx={8}
                    fill="color-mix(in srgb, var(--color-surface-alt) 82%, var(--color-text-primary))"
                    stroke="color-mix(in srgb, var(--color-border) 70%, transparent)"
                    strokeWidth={1}
                  />
                  <text
                    x={sectorW - 21}
                    y={headerHeight / 2 + 3}
                    textAnchor="middle"
                    fontSize={9}
                    fontWeight={700}
                    fill="var(--color-text-secondary)"
                    className="pointer-events-none select-none"
                  >
                    {sector.data.children?.length ?? 0}
                  </text>
                </>
              )}
              {sector.children?.map((leaf: HierarchyRectangularNode<LayoutDatum>) =>
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
