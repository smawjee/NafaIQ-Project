import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Search,
  Layers,
  X,
  ArrowRight,
  BookOpen,
  Video,
  Flame,
  CheckCircle2,
  Star,
  Trophy,
  BarChart3,
  TrendingUp,
  Wallet,
  Library,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card } from "@/components/shared/Card";
import { AiGlyph } from "@/components/icons/AiGlyph";
import { EmojiIcon } from "@/components/icons/icons";
import { LESSONS, GLOSSARY } from "@/lib/finance/data";
import { LEARNING_PATHS, LESSON_CONTENT, lessonId } from "@/lib/learn/data";
import { useLearn } from "@/hooks/learn/use-learn";
import { useGlossarySearch, useLearnRagStatus } from "@/hooks/learn/use-learn-search";
import { AnimatedBar } from "@/components/shared/CountUpNumber";
import { useLang } from "@/hooks/use-lang";
import { LearnSearchBox } from "@/components/learn/LearnSearchBox";
import { XP_GOAL } from "@/features/learn/hub/hub.data";
import { StatPill } from "@/features/learn/hub/components/StatPill";
import { CompletionRing } from "@/features/learn/hub/components/CompletionRing";
import { HubChatPanel } from "@/features/learn/hub/components/HubChatPanel";
import { FlashcardModal } from "@/features/learn/hub/components/FlashcardModal";

export function LearnHub() {
  const { xp, statusOf, pathProgress } = useLearn();
  const { enabled: ragSearchEnabled } = useLearnRagStatus();
  const { t, lang } = useLang();
  const [search, setSearch] = useState("");
  const [flashcards, setFlashcards] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const lessonsDone = useMemo(
    () => LESSONS.filter((l) => statusOf(lessonId(l.title)) === "complete").length,
    [statusOf],
  );

  const q = search.trim().toLowerCase();
  const terms = GLOSSARY.filter(
    (t) =>
      !q ||
      t.en.toLowerCase().includes(q) ||
      t.ur.toLowerCase().includes(q) ||
      t.def.toLowerCase().includes(q),
  );

  // Semantic fallback: the substring filter above stays the instant layer (it
  // is free and fires on every keystroke); the API is consulted only when that
  // finds nothing. That is what turns "market dropping a lot" into Bear Market
  // without spending a request on every character typed.
  const { results: semanticTerms, loading: semanticLoading } = useGlossarySearch(
    search,
    lang,
    terms.length === 0,
  );
  const xpPct = Math.min(100, Math.round((xp / XP_GOAL) * 100));

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-24 lg:pb-16">
      {/* Hero */}
      <LearnHubHero
        xp={xp}
        xpPct={xpPct}
        lessonsDone={lessonsDone}
        statusOf={statusOf}
        pathProgress={pathProgress}
        ragSearchEnabled={ragSearchEnabled}
        onAskAi={() => setChatOpen(true)}
        onFlashcards={() => setFlashcards(true)}
      />
      <Card hover={false} className="hidden bg-gradient-to-br from-ai-tint to-surface">
        <h1 className="font-nastaliq text-2xl text-text-primary">سمجھو، سیکھو، بڑھو</h1>
        <p className="text-sm font-semibold text-text-primary">Samjho, Seekho, Barho</p>
        <p className="mt-1 text-sm text-text-secondary">
          {t("From KSE basics to technical analysis — in plain Urdu and English.")}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="rounded-[4px] bg-elevated px-2 py-1 text-xs font-medium text-text-secondary">
            {t("Beginner Investor")}
          </span>
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-medium text-text-muted">{t("Level Progress")}</span>
            <div className="flex items-center gap-2">
              <div className="h-2 w-40 overflow-hidden rounded-full bg-elevated">
                <AnimatedBar value={xpPct} className="bg-bull" />
              </div>
              <span className="font-mono text-xs tabular-nums text-text-muted">
                {xp} / {XP_GOAL} XP
              </span>
            </div>
          </div>
        </div>

        {/* LearnHub content search — only when the RAG backend flag is on */}
        {ragSearchEnabled && (
          <div className="mt-4 max-w-xl">
            <LearnSearchBox />
          </div>
        )}

        {/* Learning stats bar */}
        <div className="mt-4 flex flex-wrap gap-2">
          <StatPill icon={Flame} label={t("5 Day Streak")} color="#f59e0b" />
          <StatPill
            icon={CheckCircle2}
            label={`${lessonsDone} ${t("Lessons Done")}`}
            color="#00d4aa"
          />
          <StatPill icon={Star} label={`${xp} ${t("XP Earned")}`} color="#eab308" />
          <StatPill icon={Trophy} label={t("Beginner Level")} color="#8b5cf6" />
        </div>
      </Card>

      {/* Learning Paths */}
      <section>
        <h3 className="text-sm font-semibold text-text-primary">{t("Learning Paths")}</h3>
        <p className="mb-3 text-xs text-text-secondary">
          {t("Follow a structured track or explore freely")}
        </p>
        <div className="scrollbar-none flex gap-3 overflow-x-auto pb-2">
          {LEARNING_PATHS.map((p) => {
            const progress = pathProgress(p.lessonIds);
            const firstUnfinished =
              p.lessonIds.find((l) => statusOf(l) !== "complete") ?? p.lessonIds[0];
            const PathIcon =
              (
                {
                  "psx-starter": BarChart3,
                  technical: TrendingUp,
                  islamic: Library,
                  personal: Wallet,
                } as Record<string, LucideIcon>
              )[p.id] ?? BookOpen;
            return (
              <div
                key={p.id}
                className="group min-w-[220px] flex-1 rounded-[12px] border border-border bg-surface p-5 transition-all hover:-translate-y-0.5 hover:border-border-hover hover:shadow-[0_8px_30px_rgba(0,0,0,0.4)]"
                style={{ borderLeft: `3px solid ${p.accent}` }}
              >
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-border"
                  style={{ background: `${p.accent}14`, color: p.accent }}
                >
                  <PathIcon className="h-[18px] w-[18px]" strokeWidth={1.5} />
                </div>
                <div className="mt-2 text-sm font-semibold text-text-primary">{t(p.title)}</div>
                <div className="mt-0.5 text-xs text-text-secondary">{t(p.description)}</div>
                <div className="mt-2 font-mono text-[11px] text-text-muted">
                  {p.lessonIds.length} {t("lessons")} · {t("Est:")} {p.estMin} {t("min")}
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-elevated">
                  <AnimatedBar value={progress} style={{ background: p.accent }} glow={false} />
                </div>
                <div className="mt-1 text-[10px] font-medium text-text-muted">
                  {progress}% {t("complete")}
                </div>
                <Link
                  to="/learn/lesson/$id"
                  params={{ id: firstUnfinished }}
                  className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-[8px] px-3 py-2 text-xs font-semibold transition-colors"
                  style={{ background: `${p.accent}1a`, color: p.accent }}
                >
                  {progress > 0 ? t("Continue Path") : t("Start Path")}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            );
          })}
        </div>
      </section>

      {/* Lessons */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Lessons")}</h3>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {LESSONS.map((l) => {
            const id = lessonId(l.title);
            const status = statusOf(id);
            const content = LESSON_CONTENT[id];
            const isVideo = content?.type === "video" && !!content?.videoUrl;
            return (
              <Link key={l.title} to="/learn/lesson/$id" params={{ id }}>
                <Card className="group h-full transition-all hover:-translate-y-[3px] hover:border-bull">
                  <div className="flex items-start gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-border bg-elevated text-text-secondary">
                      <EmojiIcon emoji={l.emoji} size={18} />
                    </span>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-text-primary">{t(l.title)}</div>
                      <div className="mt-1 flex items-center gap-1.5 text-[10px]">
                        <span className="rounded-[4px] bg-elevated px-1.5 py-0.5 text-text-muted">
                          {l.duration}
                        </span>
                        <span className="rounded-[4px] bg-elevated px-1.5 py-0.5 text-text-muted">
                          {t(l.level)}
                        </span>
                      </div>
                    </div>
                    <CompletionRing status={status} />
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="inline-flex items-center gap-1 rounded-[4px] bg-elevated px-2 py-0.5 text-[10px] text-text-secondary">
                      {isVideo ? (
                        <>
                          <Video className="h-3 w-3" strokeWidth={1.5} /> {t("Video + Article")}
                        </>
                      ) : (
                        <>
                          <BookOpen className="h-3 w-3" strokeWidth={1.5} /> {t("Article")}
                        </>
                      )}
                    </span>
                    {status === "in-progress" && (
                      <span className="text-[10px] font-medium text-warning">
                        {t("In Progress")}
                      </span>
                    )}
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Glossary */}
      {/* id: LearnSearchBox scrolls glossary hits here — the box lives on this
          same route, so navigating to /learn would be a no-op. */}
      <section id="learn-glossary" className="scroll-mt-24">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-text-primary">{t("Glossary")}</h3>
          <button
            onClick={() => setFlashcards(true)}
            className="inline-flex items-center gap-1.5 rounded-[6px] border border-bull/40 bg-bull/10 px-3 py-1.5 text-xs font-semibold text-bull hover:bg-bull/20"
          >
            <Layers className="h-3.5 w-3.5" /> {t("Flashcard Mode")}
          </button>
        </div>
        <div className="mb-3 flex items-center gap-2 rounded-[6px] border border-border bg-surface px-3 py-2">
          <Search className="h-4 w-4 text-text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("Search terms")}
            className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
          />
        </div>
        <Accordion type="multiple" className="space-y-2">
          {terms.map((term) => (
            <AccordionItem
              key={term.en}
              value={term.en}
              className="rounded-btn border border-border bg-surface px-3"
            >
              <AccordionTrigger className="py-2 text-sm font-medium hover:no-underline">
                <span className="flex w-full items-center justify-between gap-2">
                  <span>{t(term.en)}</span>
                  <span className="font-urdu text-base text-text-secondary">{term.ur}</span>
                </span>
              </AccordionTrigger>
              <AccordionContent className="pb-3">
                <p className="text-xs leading-relaxed text-text-secondary">{t(term.def)}</p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
        {terms.length === 0 && semanticTerms.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-text-muted">{t("Closest matches")}</p>
            {semanticTerms.map((r) => (
              <div key={r.title} className="rounded-btn border border-border bg-surface px-3 py-2">
                <div className="text-sm font-medium text-text-primary">{t(r.title)}</div>
                <p
                  className="mt-0.5 text-xs leading-relaxed text-text-secondary"
                  dir={lang === "ur" && r.snippet_ur ? "rtl" : undefined}
                >
                  {/* Snippets are never run through t(): it matches whole
                      canonical strings, and a partial snippet would fall
                      through untranslated. The backend ships the Urdu. */}
                  {lang === "ur" && r.snippet_ur ? r.snippet_ur : r.snippet_en}
                </p>
              </div>
            ))}
          </div>
        )}
        {terms.length === 0 && semanticTerms.length === 0 && (
          <div className="rounded-btn border border-dashed border-border bg-surface p-6 text-center text-sm text-text-muted">
            {semanticLoading ? t("Searching…") : `${t("No terms found for")} “${search}”`}
          </div>
        )}
      </section>

      {flashcards && <FlashcardModal onClose={() => setFlashcards(false)} />}

      {/* Floating AI Tutor button */}
      <button
        onClick={() => setChatOpen(true)}
        className="fixed right-4 bottom-20 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-bull text-bull-foreground shadow-[0_4px_24px_rgba(0,0,0,0.5)] hover:brightness-110 lg:bottom-8"
        aria-label={t("Ask AI Tutor")}
      >
        <AiGlyph className="h-6 w-6" />
      </button>

      {/* AI Tutor chat sheet */}
      {chatOpen && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end sm:items-end sm:justify-end sm:p-6"
          onClick={() => setChatOpen(false)}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="relative flex max-h-[70dvh] flex-col overflow-hidden rounded-t-[16px] border-t border-border bg-sidebar sm:max-h-[calc(100dvh-5rem)] sm:h-[560px] sm:w-[380px] sm:rounded-[16px] sm:border"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-border sm:hidden" />
            <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-text-primary">
                <AiGlyph className="h-4 w-4 text-bull" /> {t("Ask AI Tutor")}
              </span>
              <button onClick={() => setChatOpen(false)} aria-label="Close">
                <X className="h-5 w-5 text-text-secondary" />
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <HubChatPanel />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LearnHubHero({
  xp,
  xpPct,
  lessonsDone,
  statusOf,
  pathProgress,
  ragSearchEnabled,
  onAskAi,
  onFlashcards,
}: {
  xp: number;
  xpPct: number;
  lessonsDone: number;
  statusOf: ReturnType<typeof useLearn>["statusOf"];
  pathProgress: ReturnType<typeof useLearn>["pathProgress"];
  ragSearchEnabled: boolean;
  onAskAi: () => void;
  onFlashcards: () => void;
}) {
  const { t } = useLang();
  const totalLessons = LESSONS.length;
  const nextLessonId =
    LESSONS.map((l) => lessonId(l.title)).find((id) => statusOf(id) !== "complete") ??
    lessonId(LESSONS[0].title);
  const nextLesson = LESSON_CONTENT[nextLessonId];
  const activePath =
    LEARNING_PATHS.find((p) => p.lessonIds.includes(nextLessonId)) ?? LEARNING_PATHS[0];
  const activePathProgress = pathProgress(activePath.lessonIds);

  return (
    <section className="overflow-hidden rounded-[18px] border border-border bg-surface shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="p-5 sm:p-7">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-bull/25 bg-bull/10 px-3 py-1 text-xs font-semibold text-bull">
              <Library className="h-3.5 w-3.5" strokeWidth={1.7} />
              {t("Learn Hub")}
            </span>
            <span className="rounded-full border border-border bg-elevated px-3 py-1 text-xs font-medium text-text-secondary">
              {t("Urdu + English")}
            </span>
          </div>

          <div className="mt-6 max-w-2xl">
            <div className="font-nastaliq text-3xl leading-tight text-text-primary sm:text-4xl">
              سمجھو، سیکھو، بڑھو
            </div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-text-primary sm:text-4xl">
              {t("Build PSX confidence one lesson at a time")}
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-secondary sm:text-base">
              {t(
                "Practical investing lessons, quizzes, glossary search, and an AI tutor built for Pakistan's market.",
              )}
            </p>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            <Link
              to="/learn/lesson/$id"
              params={{ id: nextLessonId }}
              className="inline-flex items-center gap-2 rounded-[10px] bg-bull px-4 py-2.5 text-sm font-semibold text-bull-foreground transition hover:brightness-110"
            >
              {lessonsDone > 0 ? t("Continue Learning") : t("Start Learning")}
              <ArrowRight className="h-4 w-4" />
            </Link>
            <button
              onClick={onAskAi}
              className="inline-flex items-center gap-2 rounded-[10px] border border-border bg-elevated px-4 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-hover"
            >
              <AiGlyph className="h-4 w-4 text-bull" />
              {t("Ask AI Tutor")}
            </button>
            <button
              onClick={onFlashcards}
              className="inline-flex items-center gap-2 rounded-[10px] border border-border bg-elevated px-4 py-2.5 text-sm font-semibold text-text-primary transition hover:bg-hover"
            >
              <Layers className="h-4 w-4 text-text-secondary" />
              {t("Flashcards")}
            </button>
          </div>

          {ragSearchEnabled && (
            <div className="mt-6 max-w-2xl rounded-[14px] border border-border bg-elevated p-2">
              <LearnSearchBox />
            </div>
          )}

          <div className="mt-6 grid gap-2 sm:grid-cols-4">
            <HeroMetric icon={Flame} label="Streak" value="5 days" tone="text-warning" />
            <HeroMetric
              icon={CheckCircle2}
              label="Lessons done"
              value={`${lessonsDone}/${totalLessons}`}
              tone="text-bull"
            />
            <HeroMetric icon={Star} label="XP earned" value={`${xp}`} tone="text-gold" />
            <HeroMetric icon={Trophy} label="Level" value="Beginner" tone="text-ai" />
          </div>
        </div>

        <div className="border-t border-border bg-elevated/55 p-5 sm:p-6 lg:border-l lg:border-t-0">
          <div className="flex h-full flex-col justify-between gap-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                {t("Continue next")}
              </div>
              <div className="mt-3 rounded-[14px] border border-border bg-surface p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-text-primary">
                      {t(nextLesson?.title ?? "What is a Candlestick?")}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-secondary">
                      {t(nextLesson?.subtitle ?? "Learn the basics before you trade.")}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-bull/10 px-2 py-1 text-[10px] font-semibold text-bull">
                    +50 XP
                  </span>
                </div>
                <div className="mt-4 flex items-center justify-between text-[11px] text-text-muted">
                  <span>{t(activePath.title)}</span>
                  <span className="font-mono tabular-nums">{activePathProgress}%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
                  <AnimatedBar
                    value={activePathProgress}
                    style={{ background: activePath.accent }}
                  />
                </div>
                <Link
                  to="/learn/lesson/$id"
                  params={{ id: nextLessonId }}
                  className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-[10px] border border-border bg-elevated px-3 py-2 text-sm font-semibold text-text-primary transition hover:border-bull/40 hover:text-bull"
                >
                  {t("Open lesson")}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="font-semibold text-text-secondary">{t("Level Progress")}</span>
                <span className="font-mono tabular-nums text-text-muted">
                  {xp} / {XP_GOAL} XP
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-surface">
                <AnimatedBar value={xpPct} className="bg-bull" />
              </div>
              <div className="mt-3 rounded-[12px] border border-border bg-surface px-3 py-2 text-xs leading-relaxed text-text-secondary">
                {t(
                  "Complete quizzes to unlock deeper investing tracks and keep your streak alive.",
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function HeroMetric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone: string;
}) {
  const { t } = useLang();
  return (
    <div className="rounded-[12px] border border-border bg-elevated px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-muted">
        <Icon className={`h-3.5 w-3.5 ${tone}`} strokeWidth={1.7} />
        {t(label)}
      </div>
      <div className="mt-1 font-mono text-sm font-bold tabular-nums text-text-primary">
        {t(value)}
      </div>
    </div>
  );
}
