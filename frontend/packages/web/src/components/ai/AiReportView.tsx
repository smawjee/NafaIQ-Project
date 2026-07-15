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
 *   - "nudge":              paragraphs only (no considerations, no citations) — for
 *                           dashboard recommendation cards where the surface
 *                           promise is a single observation, not a deep report.
 */
import { useLang } from "@/hooks/use-lang";
import type { ReportCitation, ReportContent } from "@/lib/ai/reports-client";
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

  return (
    <div dir={isUrdu ? "rtl" : "ltr"} className={cn(isUrdu && "font-urdu", "space-y-4")}>
      {report.headline && (
        <p className="text-base font-semibold leading-relaxed text-text-primary">
          {report.headline}
        </p>
      )}

      {report.observations?.length > 0 &&
        (variant === "compact" ? (
          <ul className="space-y-2">
            {report.observations.map((o, i) => (
              <li key={i} className="flex gap-2 text-sm leading-relaxed text-text-secondary">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-ai" />
                <span>{o}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div>
            {report.observations.map((o, i) => (
              <p key={i} className="mb-2 text-sm leading-relaxed text-text-secondary last:mb-0">
                {o}
              </p>
            ))}
          </div>
        ))}

      {showDeep && report.considerations?.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t("Things to consider")}
          </h4>
          {report.considerations.map((c, i) => (
            <div
              key={i}
              className="rounded-[10px] border border-border border-l-4 border-l-ai bg-ai-tint p-3"
            >
              <p className="text-sm leading-relaxed text-text-primary">{c.consideration}</p>
              <p className="mt-1 text-xs italic leading-relaxed text-text-secondary">{c.hedge}</p>
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
          {report.disclaimer}
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
