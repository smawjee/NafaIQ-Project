/**
 * Stock Analysis report card (spec §3.2).
 *
 * Renders the verified `POST /api/ai/report/stock/{symbol}` output as
 * educational prose. Per spec §2 the new pipeline emits narrative only — no
 * directional signal label, no setup-strength badge. The technical setup is
 * a separate surface and is intentionally NOT rendered here.
 *
 * 503 (model pending / unavailable) is recoverable: we render the same
 * "Coming soon" empty state as the rest of the verified surfaces so the
 * page never blanks on a missing model.
 */
import { Sparkles } from "lucide-react";
import { useLang } from "@/hooks/use-lang";
import { useStockAnalysisReport } from "@/hooks/ai/use-stock-analysis-report";
import { reportErrorKey } from "@/lib/ai/reports-client";
import { AiReportView } from "@/components/ai/AiReportView";
import { Card } from "@/components/shared/Card";

export function StockAnalysisReportCard({ symbol }: { symbol: string }) {
  const { t } = useLang();
  const query = useStockAnalysisReport(symbol);
  const data = query.data?.content;
  const error = query.error;

  return (
    <Card hover={false}>
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Sparkles className="h-4 w-4 text-ai" />
        {t("AI Analysis")}
      </h3>

      {/* `isLoading` only — isFetching would blank the report on refetch. */}
      {query.isLoading ? (
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <span className="h-2 w-2 animate-pulse rounded-full bg-ai" />
          {t("Analyzing fundamentals and technicals…")}
        </div>
      ) : error ? (
        <div className="rounded-[8px] border border-dashed border-border bg-surface-alt p-4 text-center">
          <div className="text-sm font-medium text-text-secondary">
            {error.code === "unavailable" ? t("Coming soon") : t(reportErrorKey(error))}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-text-muted">
            {error.code === "unavailable"
              ? t("This report is being wired to the verified pipeline. The backend is ready.")
              : t("Please try again in a moment.")}
          </p>
        </div>
      ) : data ? (
        <AiReportView report={data} />
      ) : null}
    </Card>
  );
}
