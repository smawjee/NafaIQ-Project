import { useMutation } from "@tanstack/react-query";
import { fetchQuizExplanation } from "@/lib/psx/client";
import type { ApiQuizExplanation } from "@/lib/psx/client";
import type { Lang } from "@/hooks/use-lang";

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

/**
 * On-demand AI explanation for a quiz question.
 *
 * A mutation, not a query, on purpose: it must fire only when the learner
 * explicitly asks, so a wrong answer doesn't silently spend their daily LLM
 * quota. Callers should gate the affordance on `useLearnRagStatus()` and a
 * signed-in user.
 *
 * Never rejects. Flag off (503), quota exhausted (429), signed out (401) and
 * plain network failures all resolve to `{ explanation: null, sources: [] }`,
 * which is the same shape the server returns when retrieval finds nothing to
 * ground on — so there is exactly one "no AI explanation" path to render, and
 * a quiz result screen never grows an error box.
 */
export function useQuizExplanation() {
  return useMutation<ApiQuizExplanation, never, QuizExplanationInput>({
    mutationKey: ["learn", "ai", "quiz-explanation"],
    mutationFn: (input) => fetchQuizExplanation(input).catch(() => NO_EXPLANATION),
    retry: false,
  });
}
