import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Send, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { TutorMessage } from "@/components/ai/AiText";
import { useTutorChat } from "@/hooks/learn/use-tutor-chat";
import { HUB_PRESETS } from "@/features/learn/hub/hub.data";

export function HubChatPanel() {
  const { t } = useLang();
  const { messages, loading, quotaExceeded, signedOut, send } = useTutorChat({
    lessonTitle: "PSX investing basics",
    greeting: t(
      "Hi! I'm your NafaIQ tutor. Ask me anything about PSX investing, terms, or strategies.",
    ),
    hydrate: true,
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
              <TutorMessage content={m.content} role={m.role} />
            </div>
          </div>
        ))}

        {showPresets && (
          <div className="space-y-1.5 pt-1">
            {HUB_PRESETS.map((p) => (
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
          <div className="rounded-[8px] border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            {t("Daily tutor limit reached — upgrade your plan or come back tomorrow.")}
          </div>
        )}
      </div>

      {signedOut ? (
        <div className="border-t border-border p-3 text-center">
          <Link
            to="/auth"
            className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull px-4 py-2 text-xs font-semibold text-bull-foreground hover:brightness-110"
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
            placeholder={t("Ask about investing…")}
            disabled={quotaExceeded || loading}
            className="flex-1 rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <button
            onClick={() => submit(input)}
            disabled={loading || quotaExceeded}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-bull text-bull-foreground disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
