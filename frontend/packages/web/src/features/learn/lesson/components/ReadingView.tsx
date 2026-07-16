import { VideoPlaceholder } from "@/components/shared/VideoPlaceholder";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, ArrowRight, Brain, Check, CheckCircle2, FileText } from "lucide-react";
import { EmojiIcon } from "@/components/icons/icons";
import { LESSON_CONTENT, type LessonContent } from "@/lib/learn/data";
import { useLang } from "@/hooks/use-lang";
import { ACCENT } from "@/features/learn/lesson/lesson.data";
import { Blocks } from "@/features/learn/lesson/components/Blocks";
import { VideoPlayer } from "@/features/learn/lesson/components/VideoPlayer";
import { RelatedLessons } from "@/features/learn/lesson/components/RelatedLessons";
import { LessonSummaryCard } from "@/features/learn/lesson/components/LessonSummaryCard";

export function ReadingView({
  lesson,
  showArticle,
  setShowArticle,
  prevId,
  nextId,
  onTakeQuiz,
  completed,
  onMarkWatched,
}: {
  lesson: LessonContent;
  showArticle: boolean;
  setShowArticle: (v: boolean) => void;
  prevId: string | null;
  nextId: string | null;
  onTakeQuiz: () => void;
  completed: boolean;
  onMarkWatched: () => void;
}) {
  const prev = prevId ? LESSON_CONTENT[prevId] : null;
  const next = nextId ? LESSON_CONTENT[nextId] : null;
  const { t } = useLang();

  return (
    <div className="learn-fade-in">
      {/* Hero banner */}
      <div
        className="rounded-card bg-gradient-to-br from-surface to-elevated p-6 sm:p-8"
        style={{ borderLeft: `4px solid ${ACCENT}` }}
      >
        <div
          className="flex h-12 w-12 items-center justify-center rounded-btn border border-white/[0.06] bg-elevated"
          style={{ color: ACCENT }}
        >
          <EmojiIcon emoji={lesson.emoji} size={24} />
        </div>
        <h1 className="mt-3 text-3xl font-bold text-text-primary">{t(lesson.title)}</h1>
        <p className="mt-1 text-sm text-text-secondary">{t(lesson.subtitle)}</p>
        <div className="mt-3 flex items-center gap-2 text-xs">
          <span
            className="rounded-badge px-2 py-0.5 font-semibold"
            style={{ background: `${ACCENT}1a`, color: ACCENT }}
          >
            {t(lesson.level)}
          </span>
          <span className="rounded-badge bg-elevated px-2 py-0.5 text-text-secondary">
            ⏱ {lesson.duration} {t("read")}
          </span>
          <span className="rounded-badge bg-elevated px-2 py-0.5 text-text-secondary">
            {t(lesson.category)}
          </span>
        </div>
      </div>

      {/* Video */}
      {lesson.type === "video" && lesson.videoUrl && (
        <div className="mt-6">
          <VideoPlayer url={lesson.videoUrl} />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={() => setShowArticle(!showArticle)}
              className="inline-flex items-center gap-1.5 rounded-btn border border-border px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-hover"
            >
              <FileText className="h-3.5 w-3.5" strokeWidth={1.5} />{" "}
              {showArticle ? t("Hide") : t("Read")} {t("Article Version")}
            </button>
            <button
              onClick={onMarkWatched}
              className="inline-flex items-center gap-1.5 rounded-btn bg-bull/10 px-3 py-1.5 text-xs font-semibold text-bull hover:bg-bull/20"
            >
              {t("Mark Video as Watched")} <Check className="h-3.5 w-3.5" strokeWidth={1.5} />
            </button>
          </div>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-text-muted">
            <CheckCircle2 className="h-3.5 w-3.5 text-bull" strokeWidth={1.5} />{" "}
            {t("Watch at least 80% of the video to mark as complete")}
          </p>
        </div>
      )}

      {/* Video coming soon */}
      {lesson.type === "video" && !lesson.videoUrl && <VideoPlaceholder />}

      {/* Article */}
      {(lesson.type !== "video" || !lesson.videoUrl || showArticle) && (
        <article className="mt-6">
          {lesson.sections.map((s) => (
            <section key={s.id} id={s.id} className="scroll-mt-[var(--sticky-section-scroll)]">
              <h2 className="mt-10 border-b border-border pb-3 text-2xl font-bold text-text-primary first:mt-0">
                {t(s.heading)}
              </h2>
              <Blocks blocks={s.blocks} accent={ACCENT} />
            </section>
          ))}
        </article>
      )}

      {/* Take quiz */}
      <div className="mt-10 rounded-card border border-bull/30 bg-bull/5 p-6 text-center">
        <button
          onClick={onTakeQuiz}
          className="inline-flex w-full items-center justify-center gap-2 rounded-btn bg-gradient-to-r from-bull to-[#06b6d4] px-8 py-3.5 text-base font-bold text-bull-foreground transition hover:brightness-110 sm:w-auto sm:max-w-sm"
        >
          <Brain className="h-5 w-5" /> {t("Test Your Understanding — Take the Quiz")}
        </button>
        <p className="mt-2 text-xs text-text-muted">
          {lesson.quiz.length} {t("questions")} · {t("Earn up to 50 XP")}
        </p>
        {completed && (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-bull">
            <Check className="h-3.5 w-3.5" strokeWidth={1.5} /> {t("You've completed this lesson")}
          </p>
        )}
      </div>

      {/* Prev / Next */}
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {prev ? (
          <Link
            to="/learn/lesson/$id"
            params={{ id: prev.id }}
            className="rounded-btn border border-border p-3 text-left hover:border-border-hover"
          >
            <div className="flex items-center gap-1 text-[10px] text-text-muted">
              <ArrowLeft className="h-3 w-3" strokeWidth={1.5} /> {t("Previous")}
            </div>
            <div className="text-sm font-medium text-text-primary">{t(prev.title)}</div>
          </Link>
        ) : (
          <div />
        )}
        {next ? (
          <Link
            to="/learn/lesson/$id"
            params={{ id: next.id }}
            className="rounded-btn border border-border p-3 text-right hover:border-border-hover"
          >
            <div className="flex items-center justify-end gap-1 text-[10px] text-text-muted">
              {t("Next")} <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
            </div>
            <div className="text-sm font-medium text-text-primary">{t(next.title)}</div>
          </Link>
        ) : (
          <div />
        )}
      </div>

      <LessonSummaryCard lessonId={lesson.id} />
      <RelatedLessons lessonId={lesson.id} />
    </div>
  );
}
