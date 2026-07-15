/**
 * Dashboard recommendation widget (spec §3.5).
 *
 * Fetches the daily-cached cross-domain nudge from
 * `GET /api/ai/report/dashboard-recommendation` and renders the verified
 * `headline / observations / considerations / disclaimer / citations`. The
 * compliance framing rules in the backend schemas (no free-text `action`,
 * hedge required on every consideration) make a directive structurally
 * impossible — the card stays educational.
 *
 * The `enabled` flag is the dismiss switch: once the user clicks Dismiss the
 * query stops refetching for the rest of the session.
 */
import { Link } from "@tanstack/react-router";
import { Sparkles, ExternalLink } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useDashboardRecommendation } from "@/hooks/ai/use-dashboard-recommendation";
import { reportErrorKey, ReportError } from "@/lib/ai/reports-client";
import { AiReportView } from "@/components/ai/AiReportView";
import type { ReactNode } from "react";

export function DashboardRecommendation({
  enabled = true,
  onDismiss,
  rightSlot,
}: {
  enabled?: boolean;
  onDismiss?: () => void;
  rightSlot?: ReactNode;
}) {
  const { t } = useLang();
  const query = useDashboardRecommendation(enabled);
  const data = query.data?.content;
  const error = query.error;

  if (!enabled) return null;

  // `isLoading` only — also gating on isFetching would swap the rendered
  // report back to the skeleton on every background refetch.
  if (query.isLoading) {
    return (
      <div
        data-testid="dashboard-recommendation"
        className="rounded-[14px] border border-white/[0.06] bg-surface p-5"
      >
        <div className="flex items-center gap-3">
          <Sparkles className="h-4 w-4 animate-pulse text-primary" strokeWidth={1.75} />
          <span className="text-xs text-text-muted">{t("Preparing your daily nudge…")}</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    const isUnavailable = error instanceof ReportError && error.code === "unavailable";
    return (
      <div
        data-testid="dashboard-recommendation"
        className="rounded-[14px] border border-white/[0.06] bg-surface p-5"
      >
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <Sparkles className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
            {isUnavailable ? (
              <div className="flex flex-col leading-tight">
                <span className="text-xs font-semibold text-text-primary">{t("Coming soon")}</span>
                <span className="text-[11px] text-text-muted">
                  {t("This report is being wired to the verified pipeline. The backend is ready.")}
                </span>
              </div>
            ) : (
              <span className="text-xs text-text-muted">{t(reportErrorKey(error))}</span>
            )}
          </div>
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="rounded-lg px-3 py-1.5 text-xs text-text-muted transition hover:bg-white/[0.04] hover:text-text-primary"
            >
              {t("Dismiss")}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="dashboard-recommendation"
      className="rounded-[14px] border border-white/[0.06] bg-surface p-5"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-start">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Sparkles className="h-[18px] w-[18px] text-primary" strokeWidth={1.75} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-semibold text-text-primary">{t("AI Recommendation")}</h2>
            {data.confidence != null && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                {Math.round(data.confidence)}% {t("Confidence")}
              </span>
            )}
          </div>
          <div className="mt-2">
            <AiReportView report={data} variant="nudge" />
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-stretch gap-2 md:items-end">
          {rightSlot ?? (
            <Link
              to={data.view_target || "/finance"}
              className="inline-flex items-center gap-1.5 self-start rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:brightness-110 md:self-auto"
            >
              <ExternalLink className="h-3.5 w-3.5" /> {t("View")}
            </Link>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="rounded-lg px-3 py-1.5 text-xs text-text-muted transition hover:bg-white/[0.04] hover:text-text-primary"
            >
              {t("Dismiss")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
