import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import {
  List,
  LayoutGrid,
  Flame,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Scan,
} from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { AnimatePresence, motion, useReducedMotion } from "@/components/shared/animations";
import { usePsxTreemap } from "@/hooks/psx/use-psx";
import { Treemap } from "@/features/heatmap/Treemap";
import { HeatmapLegend } from "@/features/heatmap/HeatmapLegend";
import { HeatmapSkeleton } from "@/features/heatmap/HeatmapSkeleton";
import { HeatmapEmptyState } from "@/features/heatmap/HeatmapEmptyState";
import { TopMoversView, type TopMover } from "@/features/heatmap/TopMoversView";

type TreemapData = NonNullable<ReturnType<typeof usePsxTreemap>["data"]>;
type HeatmapView = "treemap" | "sectors" | "movers";
type HeatmapSort = "size" | "change" | "volume";
type PanState = { x: number; y: number };
type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
} | null;

const NORMAL_TREEMAP_WIDTH = 1280;
const NORMAL_TREEMAP_HEIGHT = 680;
const EXPANDED_MIN_WIDTH = 1280;
const ZOOM_MIN = 1;
const ZOOM_MAX = 2.5;
const ZOOM_STEP = 0.2;

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
  const reduceMotion = useReducedMotion();
  const [highlightedSector, setHighlightedSector] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<PanState>({ x: 0, y: 0 });
  const [drag, setDrag] = useState<DragState>(null);
  const [viewerSize, setViewerSize] = useState({
    width: NORMAL_TREEMAP_WIDTH,
    height: NORMAL_TREEMAP_HEIGHT,
  });
  const expandButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const dragMovedRef = useRef(false);
  const suppressClickRef = useRef(false);
  const sectorChips = sortedTreemapData?.sectors ?? treemapData?.sectors ?? [];
  const canExpand =
    heatmapView === "treemap" && !isLoadingTreemap && Boolean(sortedTreemapData?.sectors.length);

  const expandedTreemapWidth = Math.max(EXPANDED_MIN_WIDTH, Math.round(viewerSize.width));
  const expandedTreemapHeight = Math.max(760, Math.round(viewerSize.height));
  const hasNaturalOverflow =
    expandedTreemapWidth > viewerSize.width + 8 || expandedTreemapHeight > viewerSize.height + 8;
  const canPan = expanded && (zoom > 1 || hasNaturalOverflow);

  const clampZoom = useCallback((next: number) => {
    return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(next.toFixed(2))));
  }, []);

  const clampPan = useCallback(
    (next: PanState, nextZoom = zoom): PanState => {
      const overflows =
        expandedTreemapWidth * nextZoom > viewerSize.width + 8 ||
        expandedTreemapHeight * nextZoom > viewerSize.height + 8;
      if (!overflows) return { x: 0, y: 0 };
      const maxX = Math.max(0, (expandedTreemapWidth * nextZoom - viewerSize.width) / 2 + 48);
      const maxY = Math.max(0, (expandedTreemapHeight * nextZoom - viewerSize.height) / 2 + 48);
      return {
        x: Math.max(-maxX, Math.min(maxX, next.x)),
        y: Math.max(-maxY, Math.min(maxY, next.y)),
      };
    },
    [expandedTreemapHeight, expandedTreemapWidth, viewerSize.height, viewerSize.width, zoom],
  );

  const setZoomClamped = useCallback(
    (next: number) => {
      const value = clampZoom(next);
      setZoom(value);
      setPan((prev) => clampPan(prev, value));
    },
    [clampPan, clampZoom],
  );

  const resetZoom = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const resetHeatmapView = useCallback(() => {
    onDrillUp();
    resetZoom();
  }, [onDrillUp, resetZoom]);

  const collapse = useCallback(() => {
    setExpanded(false);
    resetZoom();
    window.setTimeout(() => expandButtonRef.current?.focus(), reduceMotion ? 0 : 180);
  }, [reduceMotion, resetZoom]);

  useEffect(() => {
    if (!expanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [expanded]);

  useEffect(() => {
    if (!expanded) return;
    dialogRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        collapse();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not(:disabled), select:not(:disabled), input:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [collapse, expanded]);

  useEffect(() => {
    if (!expanded || !viewerRef.current) return;
    const element = viewerRef.current;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      window.requestAnimationFrame(() => {
        setViewerSize({
          width: Math.max(320, width),
          height: Math.max(360, height),
        });
      });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [expanded]);

  useEffect(() => {
    setPan((prev) => clampPan(prev));
  }, [clampPan, viewerSize, zoom]);

  const zoomIn = () => setZoomClamped(zoom + ZOOM_STEP);
  const zoomOut = () => setZoomClamped(zoom - ZOOM_STEP);

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    if (!expanded || !(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    setZoomClamped(zoom + (event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!canPan) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragMovedRef.current = false;
    setDrag({
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: pan.x,
      originY: pan.y,
    });
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (Math.abs(event.clientX - drag.startX) > 4 || Math.abs(event.clientY - drag.startY) > 4) {
      dragMovedRef.current = true;
    }
    setPan(
      clampPan({
        x: drag.originX + event.clientX - drag.startX,
        y: drag.originY + event.clientY - drag.startY,
      }),
    );
  };

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (drag?.pointerId === event.pointerId) {
      if (dragMovedRef.current) {
        suppressClickRef.current = true;
        window.setTimeout(() => {
          suppressClickRef.current = false;
        }, 0);
      }
      setDrag(null);
    }
  };

  const handleStockClick = (symbol: string) => {
    if (suppressClickRef.current) return;
    onStockNavigate(symbol);
  };

  const handleSectorClick = (sector: string, focusZoom = 1.18) => {
    if (suppressClickRef.current) return;
    onDrillSector(sector);
    if (expanded) {
      setZoomClamped(focusZoom);
      setPan({ x: 0, y: 0 });
    }
  };

  const heatmapControls = (isExpanded: boolean) => (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={heatmapSort}
        onChange={(e) => onHeatmapSort(e.target.value as HeatmapSort)}
        className="h-9 rounded-[6px] border border-border bg-surface px-3 text-sm text-text-primary"
        disabled={!!drilledSector}
      >
        <option value="size">{t("By Size")}</option>
        <option value="change">{t("By % Change")}</option>
        <option value="volume">{t("By Volume")}</option>
      </select>
      <div className="flex h-9 items-center gap-0.5 rounded-[6px] border border-border bg-surface p-0.5">
        <button
          type="button"
          onClick={() => onHeatmapView("treemap")}
          className={cn(
            "inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-xs font-medium transition",
            heatmapView === "treemap"
              ? "bg-bull text-bull-foreground"
              : "text-text-secondary hover:bg-hover",
          )}
          title={t("Treemap view")}
        >
          <LayoutGrid className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => onHeatmapView("sectors")}
          className={cn(
            "inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-xs font-medium transition",
            heatmapView === "sectors"
              ? "bg-bull text-bull-foreground"
              : "text-text-secondary hover:bg-hover",
          )}
          title={t("Sectors bar list")}
        >
          <List className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={() => onHeatmapView("movers")}
          className={cn(
            "inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-xs font-medium transition",
            heatmapView === "movers"
              ? "bg-bull text-bull-foreground"
              : "text-text-secondary hover:bg-hover",
          )}
          title={t("Top Movers")}
        >
          <Flame className="h-3.5 w-3.5" />
        </button>
      </div>
      {isExpanded && (
        <div className="flex h-9 items-center gap-0.5 rounded-[6px] border border-border bg-surface p-0.5">
          <button
            type="button"
            onClick={zoomOut}
            disabled={zoom <= ZOOM_MIN}
            className="inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-text-secondary transition hover:bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={t("Zoom out")}
            title={t("Zoom out")}
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={resetHeatmapView}
            disabled={!drilledSector && zoom === 1 && pan.x === 0 && pan.y === 0}
            className="inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-text-secondary transition hover:bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={t("Reset heatmap view")}
            title={t("Reset heatmap view")}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={resetZoom}
            className="inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-text-secondary transition hover:bg-hover hover:text-text-primary"
            aria-label={t("Fit to screen")}
            title={t("Fit to screen")}
          >
            <Scan className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={zoomIn}
            disabled={zoom >= ZOOM_MAX}
            className="inline-flex h-8 w-9 items-center justify-center rounded-[4px] text-text-secondary transition hover:bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={t("Zoom in")}
            title={t("Zoom in")}
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </button>
          <span className="px-2 font-mono text-[11px] text-text-muted">{zoom.toFixed(1)}x</span>
        </div>
      )}
      <button
        ref={isExpanded ? undefined : expandButtonRef}
        type="button"
        onClick={() => (isExpanded ? collapse() : setExpanded(true))}
        disabled={!isExpanded && !canExpand}
        className="inline-flex h-9 w-9 items-center justify-center rounded-[6px] border border-border bg-surface text-text-secondary transition hover:bg-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bull/60 disabled:cursor-not-allowed disabled:opacity-40"
        aria-label={isExpanded ? t("Collapse heatmap") : t("Expand heatmap")}
        title={isExpanded ? t("Collapse heatmap") : t("Expand heatmap")}
      >
        {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </button>
    </div>
  );

  const titleBlock = (isExpanded: boolean) => (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <h3
          id={isExpanded ? "expanded-sector-heatmap-title" : undefined}
          className={cn(
            "font-semibold leading-tight text-text-primary",
            isExpanded ? "text-xl" : "text-lg",
          )}
        >
          {drilledSector ? t(drilledSector) : t("Sector Heatmap")}
        </h3>
        {isExpanded && (
          <span className="rounded-full border border-bull/25 bg-bull/10 px-2 py-0.5 text-[11px] font-semibold text-bull">
            {t("Expanded view")}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-xs text-text-muted">
        {treemapData
          ? `${treemapData.sectors.length} ${t("sectors")} - ${renderedStockCount} ${t("stocks")}`
          : t("Loading...")}
      </p>
      {drilledSector && (
        <button
          type="button"
          onClick={resetHeatmapView}
          className="mt-2 text-xs font-semibold text-bull hover:text-bull/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bull/50"
        >
          {t("All sectors")} / {t(drilledSector)}
        </button>
      )}
    </div>
  );

  const sectorNavigation = (isExpanded: boolean) =>
    sectorChips.length > 0 && (
      <div
        className={cn(
          "scrollbar-none flex gap-2 overflow-x-auto pb-1",
          isExpanded ? "mt-3" : "mt-4",
        )}
        aria-label={t("Sector navigation")}
        onMouseLeave={() => setHighlightedSector(null)}
      >
        <button
          type="button"
          onClick={() => {
            onHeatmapView("treemap");
            resetHeatmapView();
          }}
          onMouseEnter={() => setHighlightedSector(null)}
          className={cn(
            "shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
            !drilledSector
              ? "border-bull/40 bg-bull/10 text-bull"
              : "border-border bg-surface text-text-secondary hover:bg-hover hover:text-text-primary",
          )}
        >
          {t("All")}
        </button>
        {sectorChips.map((sector) => {
          const active = drilledSector === sector.name;
          return (
            <button
              key={sector.name}
              type="button"
              onClick={() => {
                onHeatmapView("treemap");
                handleSectorClick(sector.name, isExpanded ? 1.18 : 1);
              }}
              onDoubleClick={() => {
                onHeatmapView("treemap");
                handleSectorClick(sector.name, 1.35);
              }}
              onMouseEnter={() => setHighlightedSector(sector.name)}
              onFocus={() => setHighlightedSector(sector.name)}
              onBlur={() => setHighlightedSector(null)}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                active
                  ? "border-bull/50 bg-bull/15 text-bull"
                  : "border-border bg-surface text-text-secondary hover:border-bull/35 hover:bg-hover hover:text-text-primary",
              )}
            >
              <span>{t(sector.name)}</span>
              <span className="rounded-full bg-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
                {sector.stock_count}
              </span>
            </button>
          );
        })}
      </div>
    );

  const heatmapBody = (isExpanded: boolean) => {
    const treemapHeight = isExpanded ? expandedTreemapHeight : NORMAL_TREEMAP_HEIGHT;
    const treemapWidth = isExpanded ? expandedTreemapWidth : NORMAL_TREEMAP_WIDTH;

    if (heatmapView === "treemap") {
      if (isLoadingTreemap) return <HeatmapSkeleton height={treemapHeight} />;
      if (!sortedTreemapData || sortedTreemapData.sectors.length === 0) {
        return <HeatmapEmptyState height={treemapHeight} />;
      }
      return (
        <div
          ref={isExpanded ? viewerRef : undefined}
          data-testid={isExpanded ? "psx-heatmap-expanded-viewer" : "psx-heatmap-scroll"}
          className={cn(
            "overflow-hidden rounded-[10px] border border-border bg-background/30 p-2",
            isExpanded ? "h-full min-h-0 touch-none" : "scrollbar-none overflow-x-auto",
            canPan ? (drag ? "cursor-grabbing" : "cursor-grab") : "",
          )}
          onWheel={isExpanded ? handleWheel : undefined}
          onPointerDown={isExpanded ? handlePointerDown : undefined}
          onPointerMove={isExpanded ? handlePointerMove : undefined}
          onPointerUp={isExpanded ? handlePointerUp : undefined}
          onPointerCancel={isExpanded ? handlePointerUp : undefined}
        >
          <div
            className={cn(isExpanded ? "origin-center" : "min-w-[1280px]")}
            style={
              isExpanded
                ? {
                    width: treemapWidth,
                    transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})`,
                    transition: drag ? "none" : "transform 180ms ease-out",
                  }
                : undefined
            }
          >
            <Treemap
              data={sortedTreemapData}
              width={treemapWidth}
              height={treemapHeight}
              drilledSector={drilledSector}
              highlightedSector={highlightedSector}
              onStockClick={handleStockClick}
              onSectorClick={(sector) => handleSectorClick(sector)}
              onSectorDoubleClick={(sector) => handleSectorClick(sector, 1.35)}
              onDrillUp={() => {
                resetHeatmapView();
              }}
            />
          </div>
        </div>
      );
    }

    if (heatmapView === "sectors") {
      return (
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
              <span className="text-text-muted">- {s.stock_count}</span>
              <div className="flex-1">
                <div className="h-4 overflow-hidden rounded bg-surface-alt">
                  <div
                    className="h-full rounded transition-all"
                    style={{
                      width: `${Math.min(Math.abs(s.avg_change_pct) * 5, 100)}%`,
                      backgroundColor:
                        (s.avg_change_pct ?? 0) >= 0 ? "var(--color-bull)" : "var(--color-bear)",
                    }}
                  />
                </div>
              </div>
              <Change pct={s.avg_change_pct ?? 0} />
            </button>
          ))}
        </div>
      );
    }

    return topMovers.length > 0 ? (
      <TopMoversView movers={topMovers} />
    ) : (
      <HeatmapSkeleton height={560} />
    );
  };

  return (
    <>
      <motion.div
        layoutId="psx-sector-heatmap-card"
        className={cn(expanded && "pointer-events-none opacity-0")}
      >
        <Card className="mt-5 overflow-hidden p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            {titleBlock(false)}
            {heatmapControls(false)}
          </div>
          {treemapData && <HeatmapLegend asOf={treemapData.as_of} />}
          {sectorNavigation(false)}
          <div className="mt-4 min-w-0">{heatmapBody(false)}</div>
        </Card>
      </motion.div>

      <AnimatePresence>
        {expanded && (
          <>
            <motion.button
              type="button"
              className="fixed inset-0 z-40 cursor-default bg-black/55 backdrop-blur-[2px]"
              aria-label={t("Collapse heatmap")}
              onClick={collapse}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduceMotion ? 0.08 : 0.22 }}
            />
            <motion.div
              ref={dialogRef}
              layoutId="psx-sector-heatmap-card"
              role="dialog"
              aria-modal="true"
              aria-labelledby="expanded-sector-heatmap-title"
              tabIndex={-1}
              className="fixed inset-0 z-50 flex p-0 outline-none sm:p-4 lg:p-6"
              initial={reduceMotion ? { opacity: 0 } : undefined}
              animate={reduceMotion ? { opacity: 1 } : undefined}
              exit={reduceMotion ? { opacity: 0 } : undefined}
              transition={{
                duration: reduceMotion ? 0.08 : 0.34,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <div className="flex min-h-0 w-full flex-col overflow-hidden rounded-none border border-border bg-surface-alt shadow-[0_24px_90px_rgba(0,0,0,0.55)] sm:rounded-[14px]">
                <div className="sticky top-0 z-10 border-b border-border bg-surface-alt/95 p-4 backdrop-blur sm:p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    {titleBlock(true)}
                    {heatmapControls(true)}
                  </div>
                  {treemapData && <HeatmapLegend asOf={treemapData.as_of} />}
                  {sectorNavigation(true)}
                </div>
                <div className="min-h-0 flex-1 p-3 sm:p-4">{heatmapBody(true)}</div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
