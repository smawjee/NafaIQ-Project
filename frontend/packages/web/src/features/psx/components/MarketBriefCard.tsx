/**
 * Market brief for the PSX page.
 *
 * A sleek horizontal trigger that opens a premium liquid-glass popup with the
 * verified daily brief from `GET /api/ai/report/market-brief`.
 *
 * Deliberately renders no signal badge and no confidence figure: the
 * market_brief spec instructs the model to "NOT emit any buy/sell signal label
 * or confidence badge", so showing one here would contradict the report.
 */
import { useEffect, useState } from "react";
import { RotateCw, Sparkles, X, ChevronRight } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useMarketBrief } from "@/hooks/ai/use-market-brief";
import { reportErrorKey, ReportError } from "@/lib/ai/reports-client";
import { AiReportView } from "@/components/ai/AiReportView";

export function MarketBriefCard() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const query = useMarketBrief();
  const { refresh, isRefreshing, refreshError } = query;
  const data = query.data?.content;
  const error = query.error;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const isUnavailable = error instanceof ReportError && error.code === "unavailable";

  return (
    <>
      {/* Trigger — a full-width glassy pill */}
      <button
        data-testid="market-brief"
        onClick={() => setOpen(true)}
        className="group relative flex w-full items-center gap-3 overflow-hidden rounded-[14px] border border-white/[0.08] bg-gradient-to-r from-ai/[0.10] via-surface to-primary/[0.08] px-4 py-3.5 text-left backdrop-blur-xl transition hover:border-ai/30 hover:from-ai/[0.16] hover:to-primary/[0.12]"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ai/15 ring-1 ring-inset ring-ai/20">
          <Sparkles
            className={`h-[18px] w-[18px] text-ai ${query.isLoading ? "animate-pulse" : ""}`}
            strokeWidth={1.75}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-text-primary">
            {t("Today's PSX market analysis")}
          </span>
          <span className="block truncate text-[11px] text-text-muted">
            {query.isLoading
              ? t("Preparing today's market brief…")
              : data?.headline || t("Tap for the AI read on today's market")}
          </span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-ai" />
      </button>

      {/* Liquid-glass popup */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
          onClick={() => setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-lg overflow-hidden rounded-t-[20px] border border-white/[0.12] bg-surface/70 shadow-[0_8px_60px_rgba(0,0,0,0.55)] backdrop-blur-2xl sm:rounded-[20px]"
          >
            <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-ai/[0.12] to-transparent" />

            <div className="relative flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ai/15 ring-1 ring-inset ring-ai/20">
                  <Sparkles className="h-4 w-4 text-ai" strokeWidth={1.75} />
                </span>
                <div className="leading-tight">
                  <h2 className="text-sm font-semibold text-text-primary">
                    {t("AI Analysis")}
                  </h2>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-ai/80">
                    {t("Data based")}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label={t("Close")}
                className="flex h-8 w-8 items-center justify-center rounded-full text-text-muted transition hover:bg-white/[0.08] hover:text-text-primary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="relative max-h-[70vh] overflow-y-auto px-5 py-4">
              {query.isLoading ? (
                <div className="flex items-center gap-3 py-6">
                  <Sparkles className="h-4 w-4 animate-pulse text-ai" strokeWidth={1.75} />
                  <span className="text-xs text-text-muted">
                    {t("Preparing today's market brief…")}
                  </span>
                </div>
              ) : error || !data ? (
                <div className="py-4 text-sm text-text-secondary">
                  {isUnavailable
                    ? t("This report is being wired to the verified pipeline. The backend is ready.")
                    : t(reportErrorKey(error))}
                </div>
              ) : (
                <AiReportView report={data} variant="narrative" />
              )}
              {refreshError && (
                <p role="status" className="mt-2 text-[11px] text-text-muted">
                  {t(reportErrorKey(refreshError))}
                </p>
              )}
            </div>

            <div className="relative flex items-center justify-end border-t border-white/[0.06] px-5 py-3">
              <button
                onClick={() => refresh()}
                disabled={isRefreshing}
                aria-label={t("Refresh market brief")}
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-text-muted transition hover:bg-white/[0.06] hover:text-text-primary disabled:opacity-50"
              >
                <RotateCw
                  className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`}
                  strokeWidth={1.75}
                />
                {isRefreshing ? t("Refreshing…") : t("Refresh")}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
