import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Send, Sparkles } from "lucide-react";
import { AiGlyph } from "@/components/icons/AiGlyph";
import { TutorMessage } from "@/components/ai/AiText";
import { type LessonContent } from "@/lib/learn/data";
import { useTutorChat } from "@/hooks/learn/use-tutor-chat";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

export function ChatPanel({
  lesson,
  activeSection,
  embedded,
}: {
  lesson: LessonContent;
  activeSection?: string;
  embedded?: boolean;
}) {
  const { t } = useLang();
  const sectionHeading = lesson.sections.find((s) => s.id === activeSection)?.heading;
  const { messages, loading, quotaExceeded, signedOut, send } = useTutorChat({
    lessonTitle: lesson.title,
    lessonContext: sectionHeading,
    greeting: `${t("Hi! I'm here to help you understand")} ${t(lesson.title)}. ${t("What would you like to know?")}`,
    projectId: lesson.projectId,
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  const showPresets = messages.length === 1 && !signedOut;

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
              <TutorMessage content={m.content} role={m.role} />
            </div>
            {i === 0 && <div className="mt-1 text-[10px] text-text-muted">{t("just now")}</div>}
          </div>
        ))}

        {showPresets && (
          <div className="space-y-1.5 pt-1">
            {lesson.presets.map((p) => (
              <button
                key={p}
                onClick={() => submit(p)}
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

        {quotaExceeded && (
          <div className="rounded-btn border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            {t("Daily tutor limit reached — upgrade your plan or come back tomorrow.")}
          </div>
        )}
      </div>

      {signedOut ? (
        <div className="border-t border-border p-3 text-center">
          <Link
            to="/auth"
            className="inline-flex items-center gap-1.5 rounded-btn bg-bull px-4 py-2 text-xs font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Sign in to chat with your tutor")}
          </Link>
        </div>
      ) : (
        <div className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(input)}
            placeholder={t("Ask about this lesson…")}
            disabled={quotaExceeded || loading}
            className="flex-1 rounded-btn border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <button
            onClick={() => submit(input)}
            disabled={loading || quotaExceeded}
            aria-label={t("Send")}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-btn bg-bull text-bull-foreground disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
