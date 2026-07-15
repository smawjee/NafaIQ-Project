/**
 * Market brief bar for the PSX page.
 *
 * Renders the verified daily brief from `GET /api/ai/report/market-brief`.
 *
 * Replaces a hardcoded block that claimed "RSI at 58", "STRONG BUY" and
 * "Confidence 72%" regardless of the actual market — the same fabricated-copy
 * problem that was removed from the Dashboard. Deliberately renders no signal
 * badge and no confidence figure: the market_brief spec instructs the model to
 * "NOT emit any buy/sell signal label or confidence badge", so showing one here
 * would contradict the report it is displaying.
 */
import { Sparkles } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useMarketBrief } from "@/hooks/ai/use-market-brief";
import { reportErrorKey, ReportError } from "@/lib/ai/reports-client";
import { AiReportView } from "@/components/ai/AiReportView";

export function MarketBriefCard() {
  const { t } = useLang();
  const query = useMarketBrief();
  const data = query.data?.content;
  const error = query.error;

  const shell = (children: React.ReactNode) => (
    <div
      data-testid="market-brief"
      className="rounded-[8px] border border-border border-l-4 border-l-ai bg-ai-tint p-4"
    >
      {children}
    </div>
  );

  // Only `isLoading` — gating on isFetching too would blank the brief on every
  // background refetch even though cached content is still valid.
  if (query.isLoading) {
    return shell(
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 animate-pulse text-ai" />
        <span className="text-xs text-text-muted">{t("Preparing today's market brief…")}</span>
      </div>,
    );
  }

  if (error || !data) {
    const isUnavailable = error instanceof ReportError && error.code === "unavailable";
    return shell(
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-text-muted" />
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
      </div>,
    );
  }

  return shell(
    <>
      <div className="flex items-center gap-2 text-sm font-semibold text-ai">
        <Sparkles className="h-4 w-4" />
        {t("AI Analysis")}
      </div>
      <div className="mt-2">
        <AiReportView report={data} variant="narrative" />
      </div>
    </>,
  );
}
