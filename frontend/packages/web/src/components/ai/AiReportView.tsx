/**
 * Renders a generated AI report body (shared by the portfolio & finance report
 * modals). The report's headline / observations / considerations / disclaimer
 * arrive already localized from the backend (the ?lang param), so only the
 * section chrome runs through t(). Direction-aware for Urdu (RTL).
 */
import { useLang } from "@/hooks/use-lang";
import type { ReportContent } from "@/lib/ai/reports-client";

export function AiReportView({ report }: { report: ReportContent }) {
  const { t, isUrdu } = useLang();

  return (
    <div dir={isUrdu ? "rtl" : "ltr"} className={isUrdu ? "font-urdu space-y-4" : "space-y-4"}>
      {report.headline && (
        <p className="text-base font-semibold leading-relaxed text-text-primary">
          {report.headline}
        </p>
      )}

      {report.observations?.length > 0 && (
        <ul className="space-y-2">
          {report.observations.map((o, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-text-secondary">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-ai" />
              <span>{o}</span>
            </li>
          ))}
        </ul>
      )}

      {report.considerations?.length > 0 && (
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
        <p className="border-t border-border pt-3 text-xs italic leading-relaxed text-text-muted">
          {report.disclaimer}
        </p>
      )}
    </div>
  );
}
