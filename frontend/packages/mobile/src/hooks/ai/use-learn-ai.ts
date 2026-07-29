// On-demand Learn AI: grounded quiz explanations + lesson summaries. Mobile
// twin of web's src/hooks/learn/{use-learn-ai,use-lesson-summary}.ts.
//
// Both are mutations, not queries, on purpose: they spend the learner's daily
// AI budget, so they must fire only on an explicit tap — opening a lesson or
// answering a quiz must never cost quota. Neither ever rejects: every failure
// (429 quota, 401 signed-out, 503 flag off, network) collapses to a safe empty
// shape so the UI renders on data alone and never grows an error box.
import { useMutation } from "@tanstack/react-query";

import { useLang, type Lang } from "@/hooks/use-lang";
import { userPost } from "@/lib/api";

// === Quiz explanation ===

export interface ApiQuizExplanation {
  /** null is a normal response — retrieval found nothing to ground on, so the
   * caller keeps its static explanation. Not an error. */
  explanation: string | null;
  /** Cited section headings, possibly empty. */
  sources: string[];
}

export interface QuizExplanationInput {
  lessonId: string;
  question: string;
  selectedOption: string;
  correctOption: string;
  lang: Lang;
}

/** Every failure mode collapses to this — the caller falls back to its static
 * explanation and never branches on error state. */
const NO_EXPLANATION: ApiQuizExplanation = { explanation: null, sources: [] };

function fetchQuizExplanation(body: QuizExplanationInput): Promise<ApiQuizExplanation> {
  return userPost<ApiQuizExplanation>("/api/learn/ai/quiz-explanation", body);
}

/**
 * On-demand AI explanation for a quiz question. Fires only when the learner
 * explicitly asks, so a wrong answer doesn't silently spend their daily LLM
 * quota. Callers should gate the affordance on `useLearnRagStatus()` + a
 * signed-in user. Never rejects.
 */
export function useQuizExplanation() {
  return useMutation<ApiQuizExplanation, never, QuizExplanationInput>({
    mutationKey: ["learn", "ai", "quiz-explanation"],
    mutationFn: (input) => fetchQuizExplanation(input).catch(() => NO_EXPLANATION),
    retry: false,
  });
}

// === Lesson summary ===

export interface ApiLessonSummary {
  /** Grounded takeaways. Empty is a normal response — nothing to summarise. */
  key_ideas: string[];
  /** Key terms worth remembering, possibly empty. */
  terms: string[];
  /** The single most common misunderstanding, or null when there isn't one. */
  pitfall: string | null;
  /** Cited section headings, possibly empty. */
  sources: string[];
}

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

/** The user-auth helpers throw `${path}: ${status} ${statusText}`, so the
 * status only survives as text — degrades safely to "no summary". */
function isRateLimited(err: unknown): boolean {
  return err instanceof Error && /\b429\b/.test(err.message);
}

function fetchLessonSummary(body: {
  lessonId: string;
  sectionId?: string;
  lang: Lang;
}): Promise<ApiLessonSummary> {
  return userPost<ApiLessonSummary>("/api/learn/ai/summary", body);
}

/**
 * Grounded summary of one lesson, on demand. Spends the learner's daily AI
 * budget — fire only from an explicit tap. Never rejects.
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
