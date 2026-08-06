import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Check } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { type LessonContent } from "@/lib/learn/data";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";
import { buildShuffled, useCountUp } from "@/features/learn/lesson/lesson.utils";

export function ResultsView({
  lesson,
  correct,
  gain,
  startXp,
  nextId,
  onRetake,
  onBackToLesson,
  onContinue,
  practice = false,
}: {
  lesson: LessonContent;
  correct: number;
  gain: number;
  startXp: number;
  nextId: string | null;
  onRetake: () => void;
  onBackToLesson: () => void;
  onContinue: () => void;
  practice?: boolean;
}) {
  const { t } = useLang();
  const total = lesson.quiz.length;
  const pct = (correct / total) * 100;
  const ringColor = correct >= total ? "#00d4aa" : correct >= 2 ? "#f59e0b" : "#ff4d4d";
  const xpVal = useCountUp(startXp, startXp + gain, 1000);
  const [drawn, setDrawn] = useState(0);
  const questions = useMemo(() => buildShuffled(lesson.quiz), [lesson.quiz]);

  useEffect(() => {
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 900);
      setDrawn(pct * p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [pct]);

  const message =
    correct >= total
      ? t("Perfect Score! Ustād level understanding!")
      : correct === 2
        ? t("Great work! One more review and you'll nail it.")
        : correct === 1
          ? t("📖 Keep learning — review the lesson and retry.")
          : t("💪 Don't give up — re-read and try again!");

  const r = 52;
  const circ = 2 * Math.PI * r;

  return (
    <div className="learn-fade-in mx-auto max-w-2xl text-center">
      <div className="text-xs text-text-muted">{t(lesson.title)}</div>
      <h2 className="text-xl font-bold text-text-primary">{t("Quiz Results")}</h2>

      <div className="relative mx-auto mt-6 h-32 w-32">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
          <circle
            cx="60"
            cy="60"
            r={r}
            fill="none"
            stroke="currentColor"
            className="text-border"
            strokeWidth="10"
          />
          <circle
            cx="60"
            cy="60"
            r={r}
            fill="none"
            stroke={ringColor}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={circ - (drawn / 100) * circ}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-bold tabular-nums" style={{ color: ringColor }}>
            {correct}/{total}
          </span>
        </div>
      </div>

      <p className="mt-4 text-base font-semibold text-text-primary">{message}</p>

      {practice ? (
        <div className="mx-auto mt-5 max-w-sm rounded-card border border-ai/30 bg-ai/5 p-5">
          <div className="text-sm font-semibold text-ai">{t("Practice result saved")}</div>
          <div className="mt-1 text-xs text-text-secondary">
            {t("Generated quizzes do not affect your XP or learning streak.")}
          </div>
        </div>
      ) : (
        <div className="mx-auto mt-5 max-w-sm rounded-card border border-bull/40 bg-bull/10 p-5">
          <div className="font-mono text-3xl font-bold text-bull">+{gain} XP</div>
          <div className="mt-1 text-xs text-text-secondary">{t("Added to your profile")}</div>
          <div className="mt-2 font-mono text-sm tabular-nums text-text-muted">
            {xpVal} {t("XP total")}
          </div>
        </div>
      )}

      {/* Review accordion */}
      <Accordion type="single" collapsible className="mt-6 space-y-2 text-start">
        {questions.map((sq, i) => (
          <AccordionItem
            key={i}
            value={`q-${i}`}
            className="rounded-btn border border-border bg-surface px-3"
          >
            <AccordionTrigger className="py-2 text-sm font-medium hover:no-underline">
              <span className="flex items-center gap-2">
                <span className="text-text-muted">Q{i + 1}</span> {t(sq.q.q)}
              </span>
            </AccordionTrigger>
            <AccordionContent className="pb-3">
              <div className="space-y-1.5 pt-0">
                {sq.options.map((o, j) => (
                  <div
                    key={j}
                    className={cn(
                      "flex items-center gap-1.5 rounded-btn px-3 py-1.5 text-xs",
                      o.isCorrect ? "bg-bull/10 text-bull" : "text-text-secondary",
                    )}
                  >
                    {o.isCorrect ? (
                      <Check className="h-3 w-3 shrink-0" strokeWidth={1.5} />
                    ) : (
                      <span className="shrink-0">•</span>
                    )}
                    {t(o.text)}
                  </div>
                ))}
                <p className="mt-2 text-xs leading-relaxed text-text-muted">
                  {t(sq.q.explanation)}
                </p>
              </div>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>

      <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
        <button
          onClick={onContinue}
          className="inline-flex items-center justify-center gap-1.5 rounded-btn bg-bull px-5 py-2.5 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Continue Learning")} <ArrowRight className="h-4 w-4" />
        </button>
        <button
          onClick={onRetake}
          className="rounded-btn border border-border px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-hover"
        >
          {t("Retake Quiz")}
        </button>
        <button
          onClick={onBackToLesson}
          className="rounded-btn border border-border px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-hover"
        >
          {t("Back to Lesson")}
        </button>
      </div>
    </div>
  );
}
