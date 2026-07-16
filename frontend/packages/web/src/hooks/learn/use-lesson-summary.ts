import { useMutation } from "@tanstack/react-query";

import { fetchLessonSummary } from "@/lib/psx/client";
import type { ApiLessonSummary } from "@/lib/psx/client";
import { useLang } from "@/hooks/use-lang";

/** An `ApiLessonSummary` plus the one failure the UI reacts to. */
export interface LessonSummary extends ApiLessonSummary {
  /** true only when the daily AI limit rejected the call (429). */
  limited: boolean;
}

const EMPTY: LessonSummary = {
  key_ideas: [],
  terms: [],
  pitfall: null,
  sources: [],
  limited: false,
};

/**
 * The user-auth helpers throw `${path}: ${status} ${statusText}`, so the status
 * only survives as text. Brittle by nature, but it degrades safely: an
 * unrecognised error is just "no summary", which is what every other failure
 * already renders.
 */
function isRateLimited(err: unknown): boolean {
  return err instanceof Error && /\b429\b/.test(err.message);
}

/**
 * Grounded summary of one lesson, on demand.
 *
 * A mutation, not a query, on purpose: this spends the learner's daily AI
 * budget, so it must fire only from an explicit click. Merely opening a lesson
 * must never cost quota, and a query — with its refetch-on-mount/-focus
 * behaviour — could not promise that.
 *
 * Never rejects. Every failure (429, 401 signed-out, 503 flag off, network)
 * resolves to an empty summary so the component renders on data alone and never
 * branches on an error state.
 */
export function useLessonSummary(lessonId: string) {
  const { lang } = useLang();

  return useMutation<LessonSummary, never, void>({
    mutationFn: () =>
      fetchLessonSummary({ lessonId, lang })
        .then((s) => ({
          // Field-by-field rather than a spread: a malformed payload should
          // still produce a renderable shape, not an undefined `.map()`.
          key_ideas: s.key_ideas ?? [],
          terms: s.terms ?? [],
          pitfall: s.pitfall ?? null,
          sources: s.sources ?? [],
          limited: false,
        }))
        .catch((err: unknown) => (isRateLimited(err) ? { ...EMPTY, limited: true } : EMPTY)),
    retry: false,
  });
}
