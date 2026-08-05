import { motion, AnimatePresence } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  CheckCircle2,
  Lightbulb,
  Loader2,
  Sparkles,
  Star,
  Target,
  Trophy,
  X,
} from "lucide-react";
import { AiText } from "@/components/ai/AiText";
import { type LessonContent } from "@/lib/learn/data";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useQuizExplanation } from "@/hooks/learn/use-learn-ai";
import { useLearnRagStatus } from "@/hooks/learn/use-learn-search";
import { cn } from "@/lib/utils";
import { buildShuffled } from "@/features/learn/lesson/lesson.utils";

export function QuizView({
  lesson,
  onExit,
  onFinish,
  practice = false,
}: {
  lesson: LessonContent;
  onExit: () => void;
  onFinish: (correct: number) => void;
  practice?: boolean;
}) {
  const { t, lang } = useLang();
  const { user } = useAuth();
  const { enabled: ragEnabled } = useLearnRagStatus();
  const explain = useQuizExplanation();
  const [questions] = useState(() => buildShuffled(lesson.quiz));
  const [current, setCurrent] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [timeLeft, setTimeLeft] = useState(30);

  const total = questions.length;
  const q = questions[current];

  const answer = useCallback(
    (optIdx: number | null) => {
      if (selected !== null) return;
      const isCorrect = optIdx !== null && q.options[optIdx].isCorrect;
      if (isCorrect) setCorrectCount((c) => c + 1);
      setSelected(optIdx ?? -1);
    },
    [selected, q],
  );

  // Timer
  useEffect(() => {
    if (selected !== null) return;
    setTimeLeft(30);
    const t = setInterval(() => {
      setTimeLeft((tl) => {
        if (tl <= 1) {
          clearInterval(t);
          answer(null);
          return 0;
        }
        return tl - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [current, selected, answer]);

  // Each question gets its own AI explanation — drop the previous one when the
  // learner moves on, so a stale answer never sits under a new question.
  const { reset: resetExplanation } = explain;
  useEffect(() => {
    resetExplanation();
  }, [current, resetExplanation]);

  // Explicit opt-in only — never fired on render, so answering wrong doesn't
  // spend the learner's daily AI budget by itself.
  function requestExplanation() {
    explain.mutate({
      lessonId: lesson.id,
      // Source (English) content text: the questions carry no stable ids, and
      // this is what the server indexed. `lang` picks the response language.
      question: q.q.q,
      // "" when the 30s timer expired without an answer — a real state the
      // backend accepts and phrases as "ran out of time".
      selectedOption: selected !== null && selected >= 0 ? q.options[selected].text : "",
      correctOption: q.options.find((o) => o.isCorrect)?.text ?? "",
      lang,
    });
  }

  function nextQuestion() {
    if (current + 1 >= total) {
      onFinish(correctCount);
    } else {
      setCurrent((c) => c + 1);
      setSelected(null);
    }
  }

  const answered = selected !== null;
  const isLast = current + 1 >= total;
  const wasCorrect = answered && q.options[selected]?.isCorrect;
  const answeredCount = current + (answered ? 1 : 0);
  const progressPct = (answeredCount / total) * 100;
  const timerColor = timeLeft > 15 ? "#00d4aa" : timeLeft > 7 ? "#f59e0b" : "#ff4d4d";
  const labels = ["A", "B", "C", "D"];

  return (
    <div className="learn-fade-in mx-auto max-w-[1100px]">
      <div className="flex justify-end">
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-bull/10 px-3 py-1 text-xs font-semibold text-bull">
          <Star className="h-3.5 w-3.5" strokeWidth={1.5} />
          {practice ? t("Practice Quiz") : t("Up to 50 XP")}
        </span>
      </div>

      {/* Header with back to lesson */}
      <div className="mt-4 flex items-center gap-3">
        <button
          onClick={onExit}
          className="flex shrink-0 items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> {t("Back to Lesson")}
        </button>
      </div>
      <h2 className="mt-3 flex items-center gap-2 text-xl font-bold text-text-primary">
        <Brain className="h-5 w-5 text-bull" strokeWidth={1.5} /> {t("Knowledge Check")}
      </h2>

      {/* Single progress indicator + running score */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-text-secondary">
            {t("Question")} {current + 1} {t("of")} {total}
          </span>
          <span className="inline-flex items-center gap-1.5 font-medium text-bull">
            <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />
            {correctCount} {t("correct so far")}
          </span>
        </div>
        <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-border">
          <motion.div
            className="h-full rounded-full bg-bull"
            initial={false}
            animate={{ width: `${progressPct}%` }}
            transition={{ type: "spring", stiffness: 160, damping: 22 }}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
        {/* Quiz card */}
        <div className="mx-auto w-full max-w-[680px] rounded-card border border-border bg-surface p-6 sm:p-8">
          {/* Timer (distinct from progress) */}
          <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-text-muted">
            <span>{t("Time left")}</span>
            <span style={{ color: timerColor }}>{answered ? "—" : `${timeLeft}s`}</span>
          </div>
          <div className="mb-6 h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full transition-all duration-1000 ease-linear"
              style={{ width: `${answered ? 0 : (timeLeft / 30) * 100}%`, background: timerColor }}
            />
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={current}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
            >
              <div className="mb-6 text-[20px] font-semibold leading-snug text-text-primary">
                {t(q.q.q)}
              </div>

              <div className="space-y-3">
                {q.options.map((opt, i) => {
                  const isSelectedWrong = answered && i === selected && !opt.isCorrect;
                  const isCorrectAns = answered && opt.isCorrect;
                  const isInactive = answered && !opt.isCorrect && i !== selected;

                  let stateCls =
                    "border-border bg-elevated hover:border-bull/50 hover:bg-bull/[0.04]";
                  let circleCls = "bg-surface text-text-secondary";
                  if (isCorrectAns) {
                    stateCls = "border-bull bg-bull/10";
                    circleCls = "bg-bull text-bull-foreground";
                  } else if (isSelectedWrong) {
                    stateCls = "border-bear bg-bear/10";
                    circleCls = "bg-bear text-white";
                  } else if (isInactive) {
                    // Legible inactive style — lighter, not low-opacity gray-on-gray
                    stateCls = "border-border/70 bg-elevated/50";
                    circleCls = "bg-surface text-text-muted";
                  }

                  return (
                    <motion.button
                      key={i}
                      disabled={answered}
                      onClick={() => answer(i)}
                      whileTap={answered ? undefined : { scale: 0.985 }}
                      animate={isCorrectAns ? { scale: [1, 1.015, 1] } : { scale: 1 }}
                      transition={{ duration: 0.3 }}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-btn border px-5 py-4 text-left transition-colors",
                        stateCls,
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold transition-colors",
                          circleCls,
                        )}
                      >
                        {labels[i]}
                      </span>
                      <span
                        className={cn(
                          "flex-1 text-sm",
                          isInactive ? "text-text-secondary" : "text-text-primary",
                          isCorrectAns && "font-semibold",
                        )}
                      >
                        {t(opt.text)}
                      </span>
                      {isCorrectAns && (
                        <CheckCircle2 className="h-5 w-5 shrink-0 text-bull" strokeWidth={2.5} />
                      )}
                      {isSelectedWrong && (
                        <X className="h-4 w-4 shrink-0 text-bear" strokeWidth={2.5} />
                      )}
                    </motion.button>
                  );
                })}
              </div>
            </motion.div>
          </AnimatePresence>

          {/* Feedback / teaching moment */}
          <AnimatePresence>
            {answered && (
              <motion.div
                initial={{ opacity: 0, height: 0, marginTop: 0 }}
                animate={{ opacity: 1, height: "auto", marginTop: 20 }}
                exit={{ opacity: 0, height: 0, marginTop: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div
                  className="rounded-btn border p-4"
                  style={{
                    background: "var(--color-elevated)",
                    borderColor: wasCorrect ? "rgba(0,212,170,0.35)" : "rgba(229,72,77,0.35)",
                    borderLeftWidth: 3,
                    borderLeftColor: wasCorrect ? "#00d4aa" : "#e5484d",
                  }}
                >
                  <div
                    className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide"
                    style={{ color: wasCorrect ? "#00d4aa" : "#e5484d" }}
                  >
                    <Lightbulb className="h-4 w-4" strokeWidth={2} />
                    {wasCorrect ? t("Correct") : t("Explanation")}
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-text-primary">
                    {t(q.q.explanation)}
                  </p>

                  {/* Opt-in deep explanation. The static line above always
                      stands on its own — everything below is additive, and
                      silently absent when the flag is off, the user is signed
                      out, the daily limit is hit, or retrieval finds nothing. */}
                  {ragEnabled && user && !explain.data && (
                    <button
                      onClick={requestExplanation}
                      disabled={explain.isPending}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-btn border border-ai/40 bg-ai/10 px-3 py-1.5 text-xs font-semibold text-ai hover:bg-ai/20 disabled:cursor-default disabled:opacity-70"
                    >
                      {explain.isPending ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
                          {t("Thinking…")}
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
                          {t("Explain in depth")}
                        </>
                      )}
                    </button>
                  )}

                  {/* The click produced nothing (429 / 401 / retrieval empty /
                      provider down — the hook collapses them all to
                      explanation: null). Say so in one muted line: the button
                      has already disappeared, and silence reads as a broken
                      feature and invites re-clicks at an endpoint that just
                      refused. The static explanation above still stands. */}
                  {explain.data && !explain.data.explanation && (
                    <p className="mt-3 text-xs text-text-muted">
                      {t("No AI explanation available right now.")}
                    </p>
                  )}

                  {explain.data?.explanation && (
                    <div className="mt-3 rounded-btn border border-ai/40 bg-ai/10 p-3">
                      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-ai">
                        <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
                        {t("AI explanation")}
                      </div>
                      <p className="mt-1.5 text-sm leading-relaxed text-text-primary">
                        <AiText text={explain.data.explanation} />
                      </p>
                      {explain.data.sources.length > 0 && (
                        <p className="mt-2 text-[11px] leading-relaxed text-text-muted">
                          {t("Based on")} {explain.data.sources.join(" · ")}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {isLast && (
                  <div className="mt-3 rounded-btn bg-bull/[0.08] px-3 py-2 text-center text-xs font-medium text-text-secondary">
                    {correctCount} {t("correct out of")} {total} {t("answered")}
                  </div>
                )}

                <button
                  onClick={nextQuestion}
                  className="mt-4 inline-flex items-center gap-1.5 rounded-btn bg-bull px-5 py-2.5 text-sm font-semibold text-bull-foreground hover:brightness-110"
                >
                  {isLast ? t("See Results") : t("Next Question")}{" "}
                  <ArrowRight className="h-4 w-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Side panel — uses the empty space for something useful */}
        <aside className="hidden xl:block">
          <div className="sticky top-[80px] space-y-4">
            <div className="rounded-card border border-border bg-surface p-5">
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-bull">
                <Sparkles className="h-3.5 w-3.5" strokeWidth={2} /> {t("Why this matters")}
              </div>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                {t(lesson.subtitle)}
              </p>
            </div>

            <div className="rounded-card border border-border bg-surface p-5">
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-text-muted">
                <Trophy className="h-3.5 w-3.5" strokeWidth={2} /> {t("Your progress")}
              </div>
              <div className="mt-3 flex items-baseline gap-1.5 font-mono">
                <span className="text-2xl font-bold tabular-nums text-bull">{correctCount}</span>
                <span className="text-sm text-text-muted">
                  / {answeredCount} {t("answered")}
                </span>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-text-secondary">
                <Target className="h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                {practice
                  ? t("Practice your understanding. Official progress is unchanged.")
                  : t("Score 2+ to complete this lesson.")}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
