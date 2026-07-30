import { Link } from "@tanstack/react-router";
import { Sparkles } from "lucide-react";

import { LESSON_CONTENT } from "@/lib/learn/data";
import { useLang } from "@/hooks/use-lang";
import { useRelatedLessons } from "@/hooks/learn/use-learn-search";

/**
 * "Related topics" — lessons ranked by content similarity to this one.
 *
 * Complements Prev/Next rather than replacing it: those walk the authored
 * course order, this surfaces conceptual neighbours the order can't express
 * (Dividends -> P/E Ratio, RSI, PSX).
 *
 * Renders nothing at all when the RAG flag is off, the API errors, or a
 * related id has no lesson body — a reading page should never show a broken
 * link or an error box for a discovery affordance.
 */
export function RelatedLessons({ lessonId }: { lessonId: string }) {
  const { t } = useLang();
  const related = useRelatedLessons(lessonId, 4);

  // The backend knows ids, not titles; resolve against the content the page
  // already has. An id without a body (content deleted since the last ingest)
  // is dropped rather than rendered as a dead link.
  const items = related
    .map((r) => ({ ...r, lesson: LESSON_CONTENT[r.lesson_id] }))
    .filter((r) => Boolean(r.lesson))
    .filter(
      (item, index, all) =>
        all.findIndex((candidate) => candidate.lesson_id === item.lesson_id) === index,
    );

  if (items.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
        <Sparkles className="h-3.5 w-3.5 text-ai" strokeWidth={1.5} />
        {t("Related topics")}
      </h3>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {items.map(({ lesson_id, lesson }) => (
          <Link
            key={lesson_id}
            to="/learn/lesson/$id"
            params={{ id: lesson_id }}
            className="rounded-btn border border-border p-3 text-start transition-colors hover:border-border-hover"
          >
            <div className="text-sm font-medium text-text-primary">{t(lesson.title)}</div>
            {lesson.sections[0] && (
              <div className="mt-0.5 line-clamp-1 text-xs text-text-muted">
                {t(lesson.sections[0].heading)}
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
