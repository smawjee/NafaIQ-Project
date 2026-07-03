import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Search,
  Check,
  Lock,
  Layers,
  X,
  RotateCcw,
  ArrowRight,
  BookOpen,
  Send,
  Sparkles,
  Video,
  PartyPopper,
  Flame,
  CheckCircle2,
  Star,
  Trophy,
  BarChart3,
  TrendingUp,
  Wallet,
  Library,
} from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Card } from "@/components/Card";
import { AiGlyph } from "@/components/AiGlyph";
import { EmojiIcon } from "@/components/icons";
import { LESSONS, GLOSSARY } from "@/lib/finance-data";
import { LEARNING_PATHS, LESSON_ID_BY_TITLE, LESSON_CONTENT, FLASHCARDS, lessonId } from "@/lib/learn-data";
import { useLearn } from "@/hooks/use-learn";
import { useServerFn } from "@tanstack/react-start";
import { askTutor } from "@/lib/learn-ai.functions";
import { cn } from "@/lib/utils";
import { AnimatedBar } from "@/components/CountUpNumber";
import { useLang } from "@/hooks/use-lang";

export const Route = createFileRoute("/learn/")({
  head: () => ({
    meta: [
      { title: "Learn Hub — NafaIQ" },
      {
        name: "description",
        content:
          "Learn PSX investing from candlesticks to halal investing — lessons, videos, quizzes and an AI tutor, in plain Urdu and English.",
      },
    ],
  }),
  component: Learn,
});

const XP_GOAL = 500;

function StatPill({ icon: Icon, label, color }: { icon: LucideIcon; label: string; color: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold"
      style={{ color, borderColor: `${color}40`, background: `${color}14` }}
    >
      <Icon className="h-3.5 w-3.5" strokeWidth={2} />
      {label}
    </span>
  );
}

function CompletionRing({ status }: { status: string }) {
  if (status === "complete") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-bull text-bull-foreground">
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }
  if (status === "in-progress") {
    return (
      <span className="relative h-6 w-6 rounded-full border-2 border-warning">
        <span className="absolute inset-y-0 left-0 w-1/2 rounded-l-full bg-warning/70" />
      </span>
    );
  }
  return <span className="h-6 w-6 rounded-full border-2 border-border" />;
}

function Learn() {
  const { xp, statusOf, pathProgress } = useLearn();
  const { t } = useLang();
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
  const xpPct = Math.min(100, Math.round((xp / XP_GOAL) * 100));

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-24 lg:pb-16">
      {/* Hero */}
      <Card hover={false} className="bg-gradient-to-br from-ai-tint to-surface">
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

        {/* Learning stats bar */}
        <div className="mt-4 flex flex-wrap gap-2">
          <StatPill icon={Flame} label={t("5 Day Streak")} color="#f59e0b" />
          <StatPill icon={CheckCircle2} label={`${lessonsDone} ${t("Lessons Done")}`} color="#00d4aa" />
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
                  className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-white/[0.06]"
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
                    <span className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-white/[0.06] bg-elevated text-text-secondary">
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
                      <span className="text-[10px] font-medium text-warning">{t("In Progress")}</span>
                    )}
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Glossary */}
      <section>
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
        {terms.length === 0 && (
          <div className="rounded-btn border border-dashed border-border bg-surface p-6 text-center text-sm text-text-muted">
            {t("No terms found for")} “{search}”
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
            className="relative h-[80vh] rounded-t-[16px] border-t border-border bg-sidebar sm:h-[560px] sm:w-[380px] sm:rounded-[16px] sm:border"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mt-2 h-1 w-10 rounded-full bg-border sm:hidden" />
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-text-primary">
                <AiGlyph className="h-4 w-4 text-bull" /> {t("Ask AI Tutor")}
              </span>
              <button onClick={() => setChatOpen(false)} aria-label="Close">
                <X className="h-5 w-5 text-text-secondary" />
              </button>
            </div>
            <div className="h-[calc(80vh-56px)] sm:h-[calc(560px-56px)]">
              <HubChatPanel />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface HubChatMsg {
  role: "user" | "assistant";
  content: string;
}

const HUB_PRESETS = [
  "What is the KSE-100 index?",
  "How do I start investing in PSX?",
  "Explain candlestick charts simply",
];

function HubChatPanel() {
  const ask = useServerFn(askTutor);
  const { t, lang } = useLang();
  const initialGreeting = t(
    "Hi! I'm your NafaIQ tutor. Ask me anything about PSX investing, terms, or strategies.",
  );
  const [messages, setMessages] = useState<HubChatMsg[]>([
    {
      role: "assistant",
      content: initialGreeting,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    setMessages((current) =>
      current.length === 1 && current[0]?.role === "assistant"
        ? [{ role: "assistant", content: initialGreeting }]
        : current,
    );
  }, [initialGreeting]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;
      const history: HubChatMsg[] = [...messages, { role: "user", content: trimmed }];
      setMessages(history);
      setInput("");
      setLoading(true);
      try {
        const res = await ask({
          data: {
            lessonTitle: "PSX investing basics",
            lang,
            messages: history.slice(-12),
          },
        });
        setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
      } catch {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: t("Sorry, something went wrong. Please try again.") },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [ask, messages, loading, lang, t],
  );

  const showPresets = messages.length === 1;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.map((m, i) => (
          <div key={i} className={cn("max-w-[88%]", m.role === "user" ? "ml-auto" : "")}>
            <div
              className={cn(
                "px-3 py-2 text-sm leading-relaxed",
                m.role === "user"
                  ? "rounded-[12px] rounded-br-none bg-bull text-bull-foreground"
                  : "rounded-[12px] rounded-bl-none bg-elevated text-text-primary",
              )}
            >
              {m.content}
            </div>
          </div>
        ))}

        {showPresets && (
          <div className="space-y-1.5 pt-1">
            {HUB_PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                className="block w-full rounded-full border border-border px-3 py-1.5 text-left text-[11px] text-text-secondary hover:border-bull hover:text-bull"
              >
                {t(p)}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Sparkles className="h-3.5 w-3.5 animate-pulse text-bull" /> {t("Thinking…")}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-border p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder={t("Ask about investing…")}
          className="flex-1 rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
        />
        <button
          onClick={() => send(input)}
          disabled={loading}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-bull text-bull-foreground disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function FlashcardModal({ onClose }: { onClose: () => void }) {
  const { t } = useLang();
  const [deck, setDeck] = useState(FLASHCARDS.map((_, i) => i));
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const total = FLASHCARDS.length;
  const done = pos >= deck.length;
  const card = !done ? FLASHCARDS[deck[pos]] : null;
  const reviewed = total - (deck.length - pos);

  function next() {
    setFlipped(false);
    setPos((p) => p + 1);
  }
  function reviewAgain() {
    setFlipped(false);
    setDeck((d) => [...d, d[pos]]);
    setPos((p) => p + 1);
  }
  function restart() {
    setDeck(FLASHCARDS.map((_, i) => i));
    setPos(0);
    setFlipped(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background p-4">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-text-primary">
          <Layers className="h-4 w-4" strokeWidth={1.5} /> {t("Flashcards")}
        </span>
        <button onClick={onClose} aria-label="Close">
          <X className="h-5 w-5 text-text-secondary" />
        </button>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-6">
        {card ? (
          <>
            <button
              onClick={() => setFlipped((f) => !f)}
              className="flip-card h-72 w-full max-w-md"
              aria-label="Flip card"
            >
              <div className={cn("flip-inner", flipped && "flipped")}>
                <div className="flip-face rounded-[16px] border border-border bg-surface p-8">
                  <div className="text-2xl font-bold text-text-primary">{t(card.front)}</div>
                  <div className="mt-3 font-urdu text-3xl text-bull">{card.ur}</div>
                  <div className="mt-6 text-xs text-text-muted">{t("Tap to flip")}</div>
                </div>
                <div className="flip-face flip-back rounded-[16px] border border-bull/40 bg-surface p-8 text-center">
                  <p className="text-sm leading-relaxed text-text-secondary">{t(card.def)}</p>
                </div>
              </div>
            </button>

            <div className="flex items-center gap-3">
              <button
                onClick={next}
                className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull px-5 py-2.5 text-sm font-semibold text-bull-foreground hover:brightness-110"
              >
                <Check className="h-4 w-4" strokeWidth={1.5} /> {t("Got it")}
              </button>
              <button
                onClick={reviewAgain}
                className="inline-flex items-center gap-1.5 rounded-[8px] border border-border px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-hover"
              >
                <RotateCcw className="h-4 w-4" /> {t("Review Again")}
              </button>
            </div>
            <div className="font-mono text-xs text-text-muted">
              {Math.min(reviewed + 1, total)} / {total} {t("terms")}
            </div>
          </>
        ) : (
          <div className="text-center">
            <PartyPopper className="mx-auto h-10 w-10 text-bull" strokeWidth={1.5} />
            <div className="mt-3 text-lg font-semibold text-text-primary">{t("Deck Complete!")}</div>
            <div className="mt-1 text-sm text-text-secondary">
              {t("You reviewed all")} {total} {t("terms.")}
            </div>
            <div className="mt-6 flex items-center justify-center gap-3">
              <button
                onClick={restart}
                className="rounded-[8px] bg-bull px-5 py-2.5 text-sm font-semibold text-bull-foreground hover:brightness-110"
              >
                {t("Restart Deck")}
              </button>
              <button
                onClick={onClose}
                className="rounded-[8px] border border-border px-5 py-2.5 text-sm font-medium text-text-secondary hover:bg-hover"
              >
                {t("Exit")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
