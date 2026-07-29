import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { InfoTip } from "@/components/shared/InfoTip";
import { Change } from "@/components/market/Change";
import { Sparkline } from "@/components/charts/charts";
import { fmtNum } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";
import { INDEX_INFO } from "@/features/psx/psx.data";
import type { DisplayIndex } from "@/features/psx/psx.utils";

export function PsxIndexOverview({
  indices,
  showAll,
  canToggle,
  onToggleShowAll,
  selectedCode,
  onSelectIndex,
}: {
  indices: DisplayIndex[];
  showAll: boolean;
  canToggle: boolean;
  onToggleShowAll: () => void;
  selectedCode?: string;
  onSelectIndex?: (idx: DisplayIndex) => void;
}) {
  const { t } = useLang();
  const railRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const rail = railRef.current;
    if (!rail) return;
    const maxScrollLeft = rail.scrollWidth - rail.clientWidth;
    setCanScrollLeft(rail.scrollLeft > 4);
    setCanScrollRight(rail.scrollLeft < maxScrollLeft - 4);
  }, []);

  useEffect(() => {
    updateScrollState();
    const rail = railRef.current;
    if (!rail) return;
    rail.addEventListener("scroll", updateScrollState, { passive: true });
    const resizeObserver = new ResizeObserver(updateScrollState);
    resizeObserver.observe(rail);
    return () => {
      rail.removeEventListener("scroll", updateScrollState);
      resizeObserver.disconnect();
    };
  }, [indices, updateScrollState]);

  const scrollRail = (direction: -1 | 1) => {
    const rail = railRef.current;
    if (!rail) return;
    rail.scrollBy({
      left: direction * Math.max(280, rail.clientWidth * 0.72),
      behavior: "smooth",
    });
  };

  return (
    <section className="min-w-0">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{t("Indices")}</h3>
        <div className="flex items-center gap-2">
          {canToggle && (
            <button
              type="button"
              onClick={onToggleShowAll}
              className="shrink-0 rounded-[6px] border border-border px-2 py-1 text-xs font-medium text-text-secondary hover:bg-hover hover:text-text-primary"
            >
              {showAll ? t("Show 4") : t("Show all")}
            </button>
          )}
        </div>
      </div>

      <div className="relative min-w-0">
        {canScrollLeft && (
          <div className="pointer-events-none absolute inset-y-0 left-0 z-10 hidden w-12 bg-gradient-to-r from-background to-transparent sm:block" />
        )}
        {canScrollRight && (
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 hidden w-12 bg-gradient-to-l from-background to-transparent sm:block" />
        )}
        {(canScrollLeft || canScrollRight) && (
          <>
            <button
              type="button"
              onClick={() => scrollRail(-1)}
              disabled={!canScrollLeft}
              className="absolute -left-6 top-1/2 z-20 hidden h-9 w-9 -translate-y-1/2 items-center justify-center rounded-[8px] border border-border bg-surface/95 text-text-secondary shadow-sm backdrop-blur transition hover:bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40 sm:inline-flex"
              aria-label={t("Scroll indices left")}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => scrollRail(1)}
              disabled={!canScrollRight}
              className="absolute right-2 top-1/2 z-20 hidden h-9 w-9 -translate-y-1/2 items-center justify-center rounded-[8px] border border-border bg-surface/95 text-text-secondary shadow-sm backdrop-blur transition hover:bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40 sm:inline-flex"
              aria-label={t("Scroll indices right")}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </>
        )}
        <div
          ref={railRef}
          aria-label={t("Index cards")}
          className="scrollbar-none -mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-1"
        >
          {indices.map((idx) => (
            <Card
              key={idx.key}
              hover={false}
              role={onSelectIndex ? "button" : undefined}
              tabIndex={onSelectIndex ? 0 : undefined}
              onClick={() => onSelectIndex?.(idx)}
              onKeyDown={(e) => {
                if (!onSelectIndex) return;
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectIndex(idx);
                }
              }}
              className={cn(
                "min-h-[138px] w-[min(78vw,270px)] shrink-0 snap-start cursor-pointer p-4 transition-colors hover:border-bull/40 sm:w-[280px] xl:w-[292px]",
                selectedCode === idx.code && "border-bull/60 bg-bull/5",
              )}
            >
              <div className="flex min-w-0 items-center gap-1.5">
                <span className="truncate text-xs font-medium text-text-secondary">{idx.name}</span>
                {INDEX_INFO[idx.name] && <InfoTip label={INDEX_INFO[idx.name]} />}
              </div>
              <div className="mt-1 truncate font-mono text-[1.35rem] font-bold leading-tight tabular-nums text-text-primary">
                {fmtNum(idx.value)}
              </div>
              <div className="flex items-center justify-between">
                <Change
                  value={`${idx.change >= 0 ? "+" : ""}${fmtNum(idx.change)}`}
                  pct={idx.changePct}
                />
              </div>
              <div className="mt-2 h-8">
                <Sparkline data={idx.spark} color="#00d4aa" />
              </div>
              {idx.date && (
                <div className="mt-1 text-[10px] font-medium text-text-muted">
                  {t("Live")} {idx.date}
                </div>
              )}
            </Card>
          ))}
        </div>
        <div className="mt-2 flex justify-end gap-1 sm:hidden">
          <button
            type="button"
            onClick={() => scrollRail(-1)}
            disabled={!canScrollLeft}
            className="inline-flex h-8 w-8 items-center justify-center rounded-[6px] border border-border text-text-secondary disabled:opacity-35"
            aria-label={t("Scroll indices left")}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => scrollRail(1)}
            disabled={!canScrollRight}
            className="inline-flex h-8 w-8 items-center justify-center rounded-[6px] border border-border text-text-secondary disabled:opacity-35"
            aria-label={t("Scroll indices right")}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </section>
  );
}
