/**
 * Dashboard recommendation (spec §3.5).
 *
 * A sleek horizontal trigger button that opens a premium liquid-glass popup with
 * the daily cross-domain nudge from `GET /api/ai/report/dashboard-recommendation`
 * (verified headline / observations / considerations / disclaimer / citations).
 * The backend compliance framing (no free-text `action`, hedge required on every
 * consideration) keeps it educational, never directive.
 *
 * `enabled` is the dismiss switch: once dismissed the query stops refetching for
 * the session. The modal open/close is local UI state — closing it does not
 * dismiss the feature.
 */
import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Sparkles, ExternalLink, RotateCw, X, ChevronRight } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useDashboardRecommendation } from "@/hooks/ai/use-dashboard-recommendation";
import { reportErrorKey, ReportError } from "@/lib/ai/reports-client";
import { AiReportView } from "@/components/ai/AiReportView";
import { viewTargetLink } from "./view-target";

export function DashboardRecommendation({
  enabled = true,
  onDismiss,
}: {
  enabled?: boolean;
  onDismiss?: () => void;
}) {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const query = useDashboardRecommendation(enabled);
  const data = query.data?.content;
  const error = query.error;
  const { refresh, isRefreshing, refreshError } = query;

  // Close on Escape while the popup is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!enabled) return null;

  const isUnavailable = error instanceof ReportError && error.code === "unavailable";

  return (
    <>
      {/* Trigger — a full-width glassy pill */}
      <button
        data-testid="dashboard-recommendation"
        onClick={() => setOpen(true)}
        className="group relative flex w-full items-center gap-3 overflow-hidden rounded-[14px] border border-white/[0.08] bg-gradient-to-r from-primary/[0.10] via-surface to-ai/[0.08] px-4 py-3.5 text-left backdrop-blur-xl transition hover:border-primary/30 hover:from-primary/[0.16] hover:to-ai/[0.12]"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/15 ring-1 ring-inset ring-primary/20">
          <Sparkles
            className={`h-[18px] w-[18px] text-primary ${query.isLoading ? "animate-pulse" : ""}`}
            strokeWidth={1.75}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-text-primary">
            {t("AI recommendation of the day")}
          </span>
          <span className="block truncate text-[11px] text-text-muted">
            {query.isLoading
              ? t("Preparing your daily nudge…")
              : data?.headline || t("Tap to see today's insight from your finances")}
          </span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-primary" />
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
            {/* Sheen: a soft top gradient for the "liquid glass" feel */}
            <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-primary/[0.12] to-transparent" />

            <div className="relative flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
              <div className="flex items-center gap-2.5">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 ring-1 ring-inset ring-primary/20">
                  <Sparkles className="h-4 w-4 text-primary" strokeWidth={1.75} />
                </span>
                <div className="leading-tight">
                  <h2 className="text-sm font-semibold text-text-primary">
                    {t("AI Recommendation")}
                  </h2>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-primary/80">
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
                  <Sparkles className="h-4 w-4 animate-pulse text-primary" strokeWidth={1.75} />
                  <span className="text-xs text-text-muted">
                    {t("Preparing your daily nudge…")}
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

            <div className="relative flex items-center justify-between gap-2 border-t border-white/[0.06] px-5 py-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => refresh()}
                  disabled={isRefreshing}
                  aria-label={t("Refresh recommendation")}
                  className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-text-muted transition hover:bg-white/[0.06] hover:text-text-primary disabled:opacity-50"
                >
                  <RotateCw
                    className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`}
                    strokeWidth={1.75}
                  />
                  {isRefreshing ? t("Refreshing…") : t("Refresh")}
                </button>
                {onDismiss && (
                  <button
                    onClick={() => {
                      setOpen(false);
                      onDismiss();
                    }}
                    className="rounded-lg px-2.5 py-1.5 text-xs text-text-muted transition hover:bg-white/[0.06] hover:text-text-primary"
                  >
                    {t("Dismiss")}
                  </button>
                )}
              </div>
              {data && (
                <Link
                  {...viewTargetLink(data.view_target)}
                  onClick={() => setOpen(false)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:brightness-110"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> {t("View")}
                </Link>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
