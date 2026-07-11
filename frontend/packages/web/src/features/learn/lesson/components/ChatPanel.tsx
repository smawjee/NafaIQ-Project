import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { AiGlyph } from "@/components/icons/AiGlyph";
import { Typewriter } from "@/components/shared/Typewriter";
import { type LessonContent } from "@/lib/learn/data";
import { askTutor } from "@/lib/learn/ai-functions";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel({
  lesson,
  activeSection,
  embedded,
}: {
  lesson: LessonContent;
  activeSection?: string;
  embedded?: boolean;
}) {
  const ask = useServerFn(askTutor);
  const { t, lang } = useLang();
  const initialGreeting = useMemo(
    () =>
      `${t("Hi! I'm here to help you understand")} ${t(lesson.title)}. ${t("What would you like to know?")}`,
    [lesson.title, t],
  );
  const [messages, setMessages] = useState<ChatMsg[]>([
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
      const history: ChatMsg[] = [...messages, { role: "user", content: trimmed }];
      setMessages(history);
      setInput("");
      setLoading(true);
      const sectionHeading = lesson.sections.find((s) => s.id === activeSection)?.heading;
      try {
        const res = await ask({
          data: {
            lessonTitle: lesson.title,
            section: sectionHeading,
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
    [ask, messages, loading, lesson, activeSection, lang, t],
  );

  const showPresets = messages.length === 1;

  return (
    <div
      className={cn(
        "flex h-full flex-col overflow-hidden rounded-card border border-border bg-surface",
        embedded && "rounded-none border-0",
      )}
    >
      <div className="border-b border-border p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-bull/15 text-bull">
            <AiGlyph className="h-3.5 w-3.5" />
          </span>
          {t("AI Tutor")}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <span className="text-[11px] text-text-secondary">
            {t("Ask anything about this lesson")}
          </span>
          <span className="rounded-full bg-ai/15 px-1.5 py-0.5 text-[9px] font-semibold text-ai">
            {t("Powered by AI")}
          </span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.map((m, i) => (
          <div key={i} className={cn("max-w-[88%]", m.role === "user" ? "ml-auto" : "")}>
            <div
              className={cn(
                "px-3 py-2 text-sm leading-relaxed",
                m.role === "user"
                  ? "rounded-card rounded-br-none bg-bull text-bull-foreground"
                  : "rounded-card rounded-bl-none bg-elevated text-text-primary",
              )}
            >
              {m.role === "assistant" ? <Typewriter key={i} text={m.content} /> : m.content}
            </div>
            {i === 0 && <div className="mt-1 text-[10px] text-text-muted">{t("just now")}</div>}
          </div>
        ))}

        {showPresets && (
          <div className="space-y-1.5 pt-1">
            {lesson.presets.map((p) => (
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
          placeholder={t("Ask about this lesson…")}
          className="flex-1 rounded-btn border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
        />
        <button
          onClick={() => send(input)}
          disabled={loading}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-btn bg-bull text-bull-foreground disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
