import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { useServerFn } from "@tanstack/react-start";
import { askTutor } from "@/features/learn/ai-functions";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { HUB_PRESETS } from "@/features/learn/hub/hub.data";

interface HubChatMsg {
  role: "user" | "assistant";
  content: string;
}

export function HubChatPanel() {
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
