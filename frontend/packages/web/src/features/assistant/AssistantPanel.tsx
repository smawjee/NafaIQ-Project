// The NafaIQ Assistant panel — what the sidebar "Ask NafaIQ AI" CTA opens.
//
// A new component, not a fork of HubChatPanel: the LearnHub tutor and its RAG
// stack are untouched and still live at /learn. This panel shares that one's
// visual language (message list, presets, quota banner, signed-out CTA) because
// they should feel like the same product, but it owns action drafts and voice.

import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Send, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { TutorMessage } from "@/components/ai/AiText";
import { useAssistantChat } from "@/features/assistant/hooks/use-assistant-chat";
import { ActionDraftCard } from "@/features/assistant/components/ActionDraftCard";
import { MicButton } from "@/features/assistant/components/MicButton";

// Chosen to advertise capability breadth: one write, one read, one alert. A
// user who only ever sees a chat box assumes it only chats.
const PRESETS = [
  "Add transaction of 1200 for food via Meezan card",
  "How much did I spend this month?",
  "Alert me when any goal reaches 50%",
  "Add MEBL to my watchlist",
];

export function AssistantPanel() {
  const { t } = useLang();
  const {
    messages,
    loading,
    quotaExceeded,
    signedOut,
    pending,
    busyAction,
    send,
    confirmPending,
    cancelPending,
  } = useAssistantChat(
    t("Hi! I can add transactions, track bills and goals, manage your portfolio and watchlist, and answer questions about your money. Type or tap the mic."),
  );

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading, pending]);

  const submit = (text: string) => {
    send(text);
    setInput("");
  };

  const showPresets = messages.length === 1 && !signedOut;
  const composerDisabled = quotaExceeded || loading;

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
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => submit(t(p))}
                className="block w-full rounded-full border border-border px-3 py-1.5 text-left text-[11px] text-text-secondary hover:border-bull hover:text-bull"
              >
                {t(p)}
              </button>
            ))}
          </div>
        )}

        {pending && (
          <ActionDraftCard
            // Remount on a new draft so the card's field state is seeded from
            // it rather than retaining the previous draft's edits.
            key={`${pending.action}-${messages.length}`}
            draft={pending}
            busy={busyAction}
            onConfirm={(args) => void confirmPending(args)}
            onCancel={cancelPending}
          />
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Sparkles className="h-3.5 w-3.5 animate-pulse text-bull" /> {t("Thinking…")}
          </div>
        )}

        {quotaExceeded && (
          <div className="rounded-[8px] border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            {t("Daily assistant limit reached — it resets tomorrow.")}
          </div>
        )}
      </div>

      {signedOut ? (
        <div className="border-t border-border p-3 text-center">
          <Link
            to="/auth"
            className="inline-flex items-center gap-1.5 rounded-[8px] bg-bull px-4 py-2 text-xs font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Sign in to use NafaIQ Assistant")}
          </Link>
        </div>
      ) : (
        <div className="flex items-center gap-2 border-t border-border p-3">
          <MicButton
            disabled={composerDisabled}
            // Lands in the input, never auto-sent: the user confirms what was
            // heard before anything acts on it.
            onTranscript={(text) => setInput((current) => (current ? `${current} ${text}` : text))}
          />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit(input)}
            placeholder={t("Ask or tell me what to do…")}
            disabled={composerDisabled}
            className="flex-1 rounded-[8px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-50"
          />
          <button
            onClick={() => submit(input)}
            disabled={composerDisabled}
            aria-label={t("Send")}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-bull text-bull-foreground disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
