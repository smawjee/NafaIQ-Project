/**
 * Renders a generated AI report body (shared by the dashboard recommendation
 * card, the portfolio + finance report modals, and the stock analysis card).
 * The report's headline / observations / considerations / disclaimer arrive
 * already localized from the backend (the ?lang param), so only the section
 * chrome runs through t(). Direction-aware for Urdu (RTL).
 *
 * `variant` controls rendering density:
 *   - "compact"   (default): bullets, full report (considerations + citations + disclaimer)
 *   - "narrative":          paragraphs, full report
 *   - "nudge":              paragraphs, considerations + disclaimer (no
 *                           citations, no deep sections) — for dashboard
 *                           recommendation cards.
 */
import { AiText } from "@/components/ai/AiText";
import { useLang } from "@/hooks/use-lang";
import type {
  ReportCitation,
  ReportContent,
  ReportMetric,
  ReportSection,
} from "@/lib/ai/reports-client";
import { cn } from "@/lib/utils";

type Variant = "compact" | "narrative" | "nudge";

export function AiReportView({
  report,
  variant = "compact",
}: {
  report: ReportContent;
  variant?: Variant;
}) {
  const { t, isUrdu } = useLang();
  const showDeep = variant !== "nudge";
  const detailedSections = getDetailedSections(report);

  return (
    <div dir={isUrdu ? "rtl" : "ltr"} className={cn(isUrdu && "font-urdu", "space-y-4")}>
      {report.headline && (
        <p className="text-base font-semibold leading-relaxed text-text-primary">
          <AiText text={report.headline} />
        </p>
      )}

      {report.observations?.length > 0 && (
        // Always bulleted: observations are discrete points, and a dotted list
        // scans far better than a wall of short paragraphs — the difference the
        // nudge and market-brief popups were losing under the narrative variant.
        <ul className="space-y-2">
          {report.observations.map((o, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-text-secondary">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-ai" />
              <span>
                <AiText text={o} />
              </span>
            </li>
          ))}
        </ul>
      )}

      {showDeep && report.executive_summary && (
        <section className="border-t border-border pt-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t("Executive summary")}
          </h4>
          <p className="text-sm leading-relaxed text-text-secondary">
            <AiText text={report.executive_summary} />
          </p>
        </section>
      )}

      {showDeep && detailedSections.length > 0 && (
        <div className="space-y-4 border-t border-border pt-4">
          {detailedSections.map((section) => (
            <DetailedSection key={section.title} section={section} />
          ))}
        </div>
      )}

      {showDeep && report.holdings_analysis && report.holdings_analysis.length > 0 && (
        <section className="space-y-2 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t("Holdings review")}
          </h4>
          <div className="space-y-2">
            {report.holdings_analysis.map((holding) => (
              <div key={holding.symbol} className="border-s-2 border-s-ai ps-3">
                <p className="text-sm font-semibold text-text-primary">{holding.symbol}</p>
                <p className="text-sm leading-relaxed text-text-secondary">
                  <AiText text={holding.summary} />
                </p>
                {holding.risk_note && (
                  <p className="mt-1 text-xs leading-relaxed text-text-muted">
                    <AiText text={holding.risk_note} />
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {showDeep && report.action_plan && report.action_plan.length > 0 && (
        <section className="space-y-2 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t("Action plan")}
          </h4>
          {report.action_plan.map((item, i) => (
            <div key={`${item.title}-${i}`} className="grid gap-1 border-s-2 border-s-ai ps-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-text-primary">
                  <AiText text={item.title} />
                </p>
                <span className="rounded-[4px] border border-border px-1.5 py-0.5 text-[11px] uppercase text-text-muted">
                  {t(item.priority)}
                </span>
                <span className="rounded-[4px] border border-border px-1.5 py-0.5 text-[11px] text-text-muted">
                  {t(item.timeframe.replaceAll("_", " "))}
                </span>
              </div>
              <p className="text-sm leading-relaxed text-text-secondary">
                <AiText text={item.rationale} />
              </p>
            </div>
          ))}
        </section>
      )}

      {showDeep && report.ml_signal_status === "not_available" && report.ml_signal_note && (
        <p className="border-t border-border pt-3 text-xs leading-relaxed text-text-muted">
          <AiText text={report.ml_signal_note} />
        </p>
      )}

      {showDeep && report.data_quality_notes && report.data_quality_notes.length > 0 && (
        <section className="space-y-1 border-t border-border pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t("Data quality")}
          </h4>
          {report.data_quality_notes.map((note, i) => (
            <p key={i} className="text-xs leading-relaxed text-text-muted">
              <AiText text={note} />
            </p>
          ))}
        </section>
      )}

      {report.considerations?.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t("Things to consider")}
          </h4>
          {report.considerations.map((c, i) => (
            <div
              key={i}
              className="rounded-[10px] border border-border border-s-4 border-s-ai bg-ai-tint p-3"
            >
              <p className="text-sm leading-relaxed text-text-primary">
                <AiText text={c.consideration} />
              </p>
              <p className="mt-1 text-xs italic leading-relaxed text-text-secondary">
                <AiText text={c.hedge} />
              </p>
            </div>
          ))}
        </div>
      )}

      {report.disclaimer && (
        <p
          className={cn(
            "text-xs italic leading-relaxed text-text-muted",
            showDeep && "border-t border-border pt-3",
          )}
        >
          <AiText text={report.disclaimer} />
        </p>
      )}

      {showDeep && report.citations && report.citations.length > 0 && (
        <details>
          <summary className="mt-3 cursor-pointer text-xs text-text-muted transition-colors hover:text-text-secondary">
            {t("View sources")}
          </summary>
          <ul className="mt-2 space-y-1 text-xs text-text-muted">
            {report.citations.map((citation: ReportCitation, i: number) => (
              <li key={i}>
                <span className="font-mono text-text-secondary">{citation.value}</span>
                {" — from "}
                {citation.source_key}
                {" (as_of: "}
                {citation.as_of}
                {")"}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function getDetailedSections(report: ReportContent): ReportSection[] {
  if (report.report_type === "finance") {
    return [
      withTitle(report.financial_health, "Financial health"),
      withTitle(report.income_analysis, "Income analysis"),
      withTitle(report.expense_analysis, "Expense analysis"),
      withTitle(report.cashflow_analysis, "Cash flow analysis"),
      withTitle(report.savings_analysis, "Savings analysis"),
      withTitle(report.budget_analysis, "Budget analysis"),
      withTitle(report.goal_progress, "Goal progress"),
      withTitle(report.emergency_fund_review, "Emergency fund review"),
    ].filter(Boolean) as ReportSection[];
  }
  if (report.report_type === "portfolio") {
    return [
      withTitle(report.portfolio_health, "Portfolio health"),
      withTitle(report.profit_loss_analysis, "Profit/loss analysis"),
      withTitle(report.allocation_analysis, "Allocation analysis"),
      withTitle(report.risk_analysis, "Risk analysis"),
    ].filter(Boolean) as ReportSection[];
  }
  return [];
}

function withTitle(section: ReportSection | null | undefined, fallback: string) {
  if (!section) return section;
  return { ...section, title: section.title || fallback };
}

function DetailedSection({ section }: { section: ReportSection }) {
  const { t } = useLang();
  return (
    <section className="space-y-2">
      <div>
        <h4 className="text-sm font-semibold text-text-primary">
          <AiText text={t(section.title)} />
        </h4>
        <p className="mt-1 text-sm leading-relaxed text-text-secondary">
          <AiText text={section.summary} />
        </p>
      </div>
      {section.supporting_metrics && section.supporting_metrics.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {section.supporting_metrics.map((metric) => (
            <MetricPill key={`${metric.label}-${metric.source_key}`} metric={metric} />
          ))}
        </div>
      )}
      {section.key_findings && section.key_findings.length > 0 && (
        <ul className="space-y-1">
          {section.key_findings.map((finding, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-text-secondary">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-ai" />
              <span>
                <AiText text={finding} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MetricPill({ metric }: { metric: ReportMetric }) {
  const { t } = useLang();
  return (
    <div className="rounded-[6px] border border-border bg-surface/70 px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-text-muted">
        <AiText text={t(metric.label)} />
      </p>
      <p className="mt-1 font-mono text-sm font-semibold text-text-primary">
        {formatMetricValue(metric.value, t)}
      </p>
      {metric.interpretation && (
        <p className="mt-1 text-xs leading-relaxed text-text-secondary">
          <AiText text={metric.interpretation} />
        </p>
      )}
    </div>
  );
}

function formatMetricValue(value: unknown, t: (key: string) => string): string {
  // Group thousands so a rupee figure like 1234567.8 reads as "1,234,567.8"
  // instead of a wall of digits. Numbers stay numerals in every language, so
  // the grouping locale is fixed to en-US. Strings arrive pre-formatted from
  // the backend — pass them through untouched.
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toLocaleString("en-US");
  }
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return `${value.length} ${t("items")}`;
  if (value && typeof value === "object") return t("Details available");
  return "--";
}
