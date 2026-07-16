import { Loader2, Sparkles } from "lucide-react";

import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { useLearnRagStatus } from "@/hooks/learn/use-learn-search";
import { useLessonSummary } from "@/hooks/learn/use-lesson-summary";

/**
 * "Key ideas from this lesson" — an on-demand, AI-generated recap grounded in
 * the lesson's own content.
 *
 * Opt-in by design: it renders as a modest button and only calls the model when
 * the learner clicks, because each call spends their daily AI budget. Nothing
 * here fires on mount.
 *
 * Like RelatedLessons, it renders nothing at all when the flag is off or the
 * result is empty — a reading page should never show an error box for an
 * optional affordance.
 */
export function LessonSummaryCard({ lessonId }: { lessonId: string }) {
  const { t } = useLang();
  const { user } = useAuth();
  const { enabled } = useLearnRagStatus();
  const { mutate, data, isPending } = useLessonSummary(lessonId);

  // `user` as well as the flag: /api/learn/ai/* needs a Supabase JWT, so for a
  // signed-out reader this button could only ever 401 and vanish on click.
  // Same gate QuizView applies to its own AI affordance.
  if (!enabled || !user) return null;

  if (isPending) {
    return (
      <p className="mt-6 inline-flex items-center gap-1.5 text-xs text-text-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> {t("Analyzing…")}
      </p>
    );
  }

  if (!data) {
    return (
      <button
        onClick={() => mutate()}
        className="mt-6 inline-flex items-center gap-1.5 rounded-btn border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-hover"
      >
        <Sparkles className="h-3.5 w-3.5 text-ai" strokeWidth={1.5} />
        {t("Key ideas from this lesson")}
      </button>
    );
  }

  // The one failure worth a word. The learner just clicked, so silence would
  // read as a broken button and invite more clicks at an endpoint that is
  // already refusing them. Every other failure stays silent below.
  if (data.limited) {
    return (
      <p className="mt-6 text-xs text-text-muted">
        {t("Daily AI limit reached — try again tomorrow.")}
      </p>
    );
  }

  // Nothing to ground on, or any other failure — render nothing.
  if (data.key_ideas.length === 0) return null;

  return (
    <div className="mt-6 rounded-card border border-ai/20 bg-ai/5 p-4">
      <h3 className="flex flex-wrap items-center gap-1.5 text-sm font-semibold text-text-primary">
        <Sparkles className="h-3.5 w-3.5 text-ai" strokeWidth={1.5} />
        {t("Key ideas from this lesson")}
        <span className="rounded-badge bg-ai/15 px-1.5 py-0.5 text-[9px] font-semibold text-ai">
          {t("AI generated")}
        </span>
      </h3>

      <ul className="mt-2 space-y-1.5 text-start text-sm text-text-secondary">
        {data.key_ideas.map((idea) => (
          <li key={idea} className="flex gap-2">
            <span className="text-ai" aria-hidden="true">
              •
            </span>
            <span>{idea}</span>
          </li>
        ))}
      </ul>

      {data.terms.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {data.terms.map((term) => (
            <span
              key={term}
              className="rounded-badge bg-elevated px-2 py-0.5 text-[11px] text-text-secondary"
            >
              {term}
            </span>
          ))}
        </div>
      )}

      {data.pitfall && (
        <div className="mt-3 rounded-btn border-s-2 border-warning bg-elevated px-2.5 py-1.5 text-start">
          <div className="text-[10px] font-semibold uppercase text-warning">
            {t("Common mistake")}
          </div>
          <p className="mt-0.5 text-xs text-text-secondary">{data.pitfall}</p>
        </div>
      )}

      {data.sources.length > 0 && (
        <p className="mt-3 text-start text-[11px] text-text-muted">
          {t("Based on")}: {data.sources.join(" · ")}
        </p>
      )}

      <p className="mt-2 text-start text-[10px] text-text-muted">
        {t("Summarised by AI from this lesson. Not financial advice.")}
      </p>
    </div>
  );
}
