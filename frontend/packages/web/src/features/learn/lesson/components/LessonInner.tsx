import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { usePersistedBool } from "@/hooks/use-persisted-bool";
import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  BookOpen,
  Cpu,
  MessageCircle,
  Sparkles,
  Target,
  Video,
  X,
} from "lucide-react";
import { AiGlyph } from "@/components/icons/AiGlyph";
import { CollapsibleColumn, CollapseHandle } from "@/components/layout/CollapsibleColumn";
import { lessonOrder, xpForScore, type LessonContent } from "@/lib/learn/data";
import { useLearn } from "@/hooks/learn/use-learn";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";
import { resultRef } from "@/features/learn/lesson/lesson.state";
import { ReadingView } from "@/features/learn/lesson/components/ReadingView";
import { QuizView } from "@/features/learn/lesson/components/QuizView";
import { ResultsView } from "@/features/learn/lesson/components/ResultsView";
import { ChatPanel } from "@/features/learn/lesson/components/ChatPanel";
import { FlashcardModal } from "@/features/learn/hub/components/FlashcardModal";
import type { StudioStudyPack } from "@nafaiq/shared";

type Mode = "reading" | "quiz" | "results";

export function LessonInner({
  lesson,
  studyPack,
  onPracticeFinish,
  onGenerateVideo,
  videoGenerating = false,
}: {
  lesson: LessonContent;
  studyPack?: StudioStudyPack;
  onPracticeFinish?: (correct: number, total: number) => void;
  onGenerateVideo?: () => void;
  videoGenerating?: boolean;
}) {
  const navigate = useNavigate();
  const { statusOf, completeLesson, bookmarks, toggleBookmark, xp } = useLearn();
  const { t } = useLang();
  const [mode, setMode] = useState<Mode>("reading");
  const [progress, setProgress] = useState(0);
  const [activeSection, setActiveSection] = useState(lesson.sections[0]?.id);
  const [chatOpen, setChatOpen] = useState(false);
  const [showArticle, setShowArticle] = useState(true);
  const [flashcardsOpen, setFlashcardsOpen] = useState(false);
  const [tocCollapsed, setTocCollapsed] = usePersistedBool("nafaiq-lesson-toc");
  const [chatCollapsed, setChatCollapsed] = usePersistedBool("nafaiq-lesson-chat");

  const practice = lesson.rewardMode === "practice";
  const order = lessonOrder();
  const idx = order.indexOf(lesson.id);
  const prevId = !practice && idx > 0 ? order[idx - 1] : null;
  const nextId = !practice && idx >= 0 && idx < order.length - 1 ? order[idx + 1] : null;
  const bookmarked = bookmarks.includes(lesson.id);

  // Reading progress on scroll
  useEffect(() => {
    if (mode !== "reading") return;
    function onScroll() {
      const el = document.documentElement;
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? Math.min(100, (el.scrollTop / max) * 100) : 0);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [mode]);

  // Active TOC section
  useEffect(() => {
    if (mode !== "reading") return;
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
    );
    lesson.sections.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
  }, [mode, lesson.sections]);

  function scrollToSection(secId: string) {
    document.getElementById(secId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Deep-link (#section-id, e.g. from LearnHub search) → scroll to it on mount.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    const raf = requestAnimationFrame(() => scrollToSection(decodeURIComponent(hash)));
    return () => cancelAnimationFrame(raf);
  }, []);

  function onQuizFinish(correct: number) {
    if (practice) {
      onPracticeFinish?.(correct, lesson.quiz.length);
      return 0;
    }
    const gain = xpForScore(correct, lesson.quiz.length);
    if (correct >= 2) completeLesson(lesson.id, gain);
    return gain;
  }

  return (
    <div data-testid="lesson-experience" className="pb-32 xl:pb-0">
      {/* Reading progress + top bar — only in reading mode; quiz/results own their nav */}
      {mode === "reading" && (
        <>
          <div className="sticky top-[var(--header-h)] z-20 h-[3px] w-full bg-border">
            <div
              className="h-full bg-bull transition-[width] duration-150"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="sticky top-[var(--topbar-h)] z-20 flex items-center gap-3 border-b border-border bg-surface px-3 py-2.5 lg:px-6">
            <Link
              to="/learn"
              className="flex shrink-0 items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
            >
              <ArrowLeft className="h-4 w-4" />{" "}
              <span className="hidden sm:inline">{t("Learn Hub")}</span>
            </Link>
            <div className="flex-1 truncate text-center text-sm font-semibold text-text-primary">
              {t(lesson.title)}
            </div>
            <button
              onClick={() => setChatOpen(true)}
              className="hidden shrink-0 items-center gap-1.5 rounded-btn bg-bull/10 px-2.5 py-1 text-xs font-semibold text-bull hover:bg-bull/20 lg:inline-flex xl:hidden"
            >
              <MessageCircle className="h-3.5 w-3.5" strokeWidth={1.5} /> {t("Ask AI")}
            </button>
            <button
              onClick={() => toggleBookmark(lesson.id)}
              aria-label={t("Bookmark")}
              className="shrink-0 text-text-secondary hover:text-bull"
            >
              {bookmarked ? (
                <BookmarkCheck className="h-5 w-5 text-bull" />
              ) : (
                <Bookmark className="h-5 w-5" />
              )}
            </button>
          </div>
        </>
      )}

      <div className="mx-auto flex max-w-app gap-5 px-3 py-5 lg:px-6">
        {/* Left TOC */}
        {mode === "reading" && (
          <CollapsibleColumn
            side="left"
            width={260}
            breakpoint="lg"
            collapsed={tocCollapsed}
            onToggle={setTocCollapsed}
            collapseButtonLabel={t("Table of contents")}
            expandButtonLabel={t("Show table of contents")}
          >
            <div className="sticky top-[var(--sticky-panel)] rounded-card border border-border bg-surface p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-text-primary">{t("In This Lesson")}</div>
                <CollapseHandle
                  side="left"
                  onClick={() => setTocCollapsed(true)}
                  ariaLabel={t("Collapse table of contents")}
                />
              </div>
              <nav className="mt-3 space-y-1 border-s border-border">
                {lesson.sections.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => scrollToSection(s.id)}
                    className={cn(
                      "-ms-px block border-s-2 py-1 ps-3 text-start text-xs transition-colors",
                      activeSection === s.id
                        ? "border-bull font-medium text-bull"
                        : "border-transparent text-text-secondary hover:text-text-primary",
                    )}
                  >
                    {t(s.heading)}
                  </button>
                ))}
              </nav>
              <div className="mt-5 space-y-1.5 border-t border-border pt-4 text-xs text-text-secondary">
                <div className="flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} /> {lesson.duration}{" "}
                  {t("read")}
                </div>
                <div className="flex items-center gap-1.5">
                  <Target className="h-3.5 w-3.5" strokeWidth={1.5} /> {t(lesson.level)}
                </div>
                <div className="flex items-center gap-1.5">
                  {lesson.type === "video" && lesson.videoUrl ? (
                    <>
                      <Video className="h-3.5 w-3.5" strokeWidth={1.5} /> {t("Video + Article")}
                    </>
                  ) : (
                    <>
                      <BookOpen className="h-3.5 w-3.5" strokeWidth={1.5} /> {t("Article")}
                    </>
                  )}
                </div>
              </div>
              <button
                onClick={() => toggleBookmark(lesson.id)}
                className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-btn border border-border px-3 py-2 text-xs font-medium text-text-secondary hover:bg-hover"
              >
                {bookmarked ? (
                  <BookmarkCheck className="h-4 w-4 text-bull" />
                ) : (
                  <Bookmark className="h-4 w-4" />
                )}
                {bookmarked ? t("Bookmarked") : t("Bookmark Lesson")}
              </button>
            </div>
          </CollapsibleColumn>
        )}

        {/* Main content */}
        <div className="min-w-0 flex-1 xl:max-w-[760px]">
          {mode === "reading" && (
            <ReadingView
              lesson={lesson}
              showArticle={showArticle}
              setShowArticle={setShowArticle}
              prevId={prevId}
              nextId={nextId}
              onTakeQuiz={() => {
                window.scrollTo({ top: 0 });
                setMode("quiz");
              }}
              completed={statusOf(lesson.id) === "complete"}
              onMarkWatched={() => completeLesson(lesson.id, 30)}
              practice={practice}
              notes={studyPack?.notes}
              keyTerms={studyPack?.keyTerms}
              suggestedTopics={studyPack?.suggestedTopics}
              sources={lesson.sources}
              onOpenFlashcards={
                studyPack?.flashcards?.length ? () => setFlashcardsOpen(true) : undefined
              }
              onGenerateVideo={onGenerateVideo}
              videoGenerating={videoGenerating}
            />
          )}

          {mode === "quiz" && (
            <QuizView
              lesson={lesson}
              practice={practice}
              onExit={() => setMode("reading")}
              onFinish={(correct) => {
                const gain = onQuizFinish(correct);
                setMode("results");
                resultRef.current = { correct, gain };
              }}
            />
          )}

          {mode === "results" && resultRef.current && (
            <ResultsView
              lesson={lesson}
              correct={resultRef.current.correct}
              gain={resultRef.current.gain}
              startXp={xp - (resultRef.current.correct >= 2 ? resultRef.current.gain : 0)}
              nextId={nextId}
              onRetake={() => setMode("quiz")}
              practice={practice}
              onBackToLesson={() => setMode("reading")}
              onContinue={() => {
                if (nextId) navigate({ to: "/learn/lesson/$id", params: { id: nextId } });
                else navigate({ to: "/learn" });
              }}
            />
          )}
        </div>

        {/* Right docked AI Tutor panel — desktop xl+ */}
        {mode === "reading" && (
          <CollapsibleColumn
            side="right"
            width={300}
            breakpoint="xl"
            collapsed={chatCollapsed}
            onToggle={setChatCollapsed}
            collapseButtonLabel={t("AI Tutor panel")}
            expandButtonLabel={t("Open AI tutor")}
          >
            <div className="sticky top-[var(--sticky-panel)] h-[calc(100dvh-var(--sticky-panel)-20px)]">
              <div className="relative h-full">
                <div className="absolute -start-2.5 top-2 z-10">
                  <CollapseHandle
                    side="right"
                    onClick={() => setChatCollapsed(true)}
                    ariaLabel={t("Collapse AI Tutor panel")}
                  />
                </div>
                <ChatPanel lesson={lesson} activeSection={activeSection} />
              </div>
            </div>
          </CollapsibleColumn>
        )}
      </div>

      {flashcardsOpen && studyPack && (
        <FlashcardModal cards={studyPack.flashcards} onClose={() => setFlashcardsOpen(false)} />
      )}

      {/* Floating AI button */}
      <button
        onClick={() => setChatOpen(true)}
        className="fixed right-4 bottom-20 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-bull text-bull-foreground shadow-[0_4px_24px_rgba(0,0,0,0.5)] hover:brightness-110 lg:bottom-8 xl:hidden"
        aria-label={t("Ask AI Tutor")}
      >
        <AiGlyph className="h-6 w-6" />
      </button>

      {/* Chat sheet — bottom sheet on mobile, right-docked panel on desktop */}
      {chatOpen && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end sm:items-end sm:justify-end sm:p-6"
          onClick={() => setChatOpen(false)}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative flex max-h-[70dvh] flex-col overflow-hidden rounded-t-card border-t border-border bg-sidebar sm:max-h-[calc(100dvh-5rem)] sm:h-[600px] sm:w-[400px] sm:rounded-card sm:border"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-border sm:hidden" />
            <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-text-primary">
                <Cpu className="h-4 w-4 text-ai" strokeWidth={1.5} /> {t("Ask AI Tutor")}
              </span>
              <button onClick={() => setChatOpen(false)} aria-label={t("Close")}>
                <X className="h-5 w-5 text-text-secondary" />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <ChatPanel lesson={lesson} activeSection={activeSection} embedded />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
