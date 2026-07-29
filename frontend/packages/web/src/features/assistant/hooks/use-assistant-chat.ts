// Chat + action state for the NafaIQ Assistant panel.
//
// Modelled on hooks/learn/use-tutor-chat.ts (plain useState + AbortController,
// tokens appended into the last assistant bubble) but deliberately a separate
// hook: the assistant additionally owns pending drafts, tiered execution, and
// cache invalidation, none of which belong in the tutor.
//
// The tiering rule lives here because it is a UI decision:
//   tier "confirm"   -> park the draft; a card renders and the user approves.
//   tier "immediate" -> execute on arrival and show an undo-able toast.
// A draft with `missing` fields is NEVER auto-executed regardless of tier —
// the agent is still collecting information.

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useLang } from "@/hooks/use-lang";
import {
  type ActionDraft,
  executeDraft,
  streamAssistant,
} from "@/lib/assistant/client";

export interface AssistantMsg {
  role: "user" | "assistant";
  content: string;
}

export function draftStatusText(draft: ActionDraft, t: (value: string) => string): string {
  if (draft.missing.length > 0) return t("Please fill the highlighted details.");
  if (draft.tier === "confirm") return t("Please review this before I save it.");
  return t("Working on that now.");
}

export function useAssistantChat(greeting: string) {
  const { lang, t } = useLang();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [messages, setMessages] = useState<AssistantMsg[]>([
    { role: "assistant", content: greeting },
  ]);
  const [loading, setLoading] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [pending, setPending] = useState<ActionDraft | null>(null);
  const [busyAction, setBusyAction] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // One id per hook mount = one Langfuse session per conversation. The chat's
  // message state lives entirely in this hook, so the id's lifetime already
  // matches the conversation's; if a clear-chat action is ever added,
  // regenerate the id there too.
  const conversationIdRef = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    setMessages((current) =>
      current.length === 1 && current[0]?.role === "assistant"
        ? [{ role: "assistant", content: greeting }]
        : current,
    );
  }, [greeting]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const { supabase } = await import("@/integrations/supabase/client");
      const { data } = await supabase.auth.getSession();
      if (!cancelled && !data.session) setSignedOut(true);
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, []);

  const invalidate = useCallback(
    (keys: string[]) => {
      for (const key of keys) void qc.invalidateQueries({ queryKey: [key] });
    },
    [qc],
  );

  /** Run a draft against the server and refresh whatever it touched. */
  const runDraft = useCallback(
    async (draft: ActionDraft, args: Record<string, unknown>) => {
      setBusyAction(true);
      try {
        const result = await executeDraft(draft.action, args, conversationIdRef.current);
        invalidate(result.invalidate);
        toast.success(t("Done"));
        setPending(null);
        return true;
      } catch (e) {
        // Domain errors are actionable ("Savings goals limit reached for Free
        // plan"), so show them and leave the card open for editing.
        toast.error(e instanceof Error ? e.message : t("Something went wrong"));
        return false;
      } finally {
        setBusyAction(false);
      }
    },
    [invalidate, t],
  );

  const confirmPending = useCallback(
    (args: Record<string, unknown>) => (pending ? runDraft(pending, args) : Promise.resolve(false)),
    [pending, runDraft],
  );

  const cancelPending = useCallback(() => setPending(null), []);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading || quotaExceeded || signedOut) return;
      setLoading(true);
      // A new question supersedes an unanswered card.
      setPending(null);

      const history: AssistantMsg[] = [...messages, { role: "user", content: trimmed }];
      setMessages([...history, { role: "assistant", content: "" }]);
      const controller = new AbortController();
      abortRef.current = controller;

      const appendToLast = (delta: string) =>
        setMessages((current) => {
          const next = [...current];
          const last = next[next.length - 1];
          if (last?.role === "assistant") {
            next[next.length - 1] = { role: "assistant", content: last.content + delta };
          }
          return next;
        });

      const replaceLast = (content: string) =>
        setMessages((current) => {
          const next = [...current];
          next[next.length - 1] = { role: "assistant", content };
          return next;
        });

      const replaceLastIfEmpty = (content: string) =>
        setMessages((current) => {
          const next = [...current];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && !last.content.trim()) {
            next[next.length - 1] = { role: "assistant", content };
          }
          return next;
        });

      void streamAssistant(
        {
          lang,
          // Drop the leading UI greeting; send the last 12 real turns.
          messages: history.filter((m, i) => !(i === 0 && m.role === "assistant")).slice(-12),
          conversation_id: conversationIdRef.current,
        },
        {
          onToken: appendToLast,
          onTool: () => {
            /* progress only; the narration that follows is the real answer */
          },
          onDraft: (draft) => {
            replaceLastIfEmpty(draftStatusText(draft, t));
            if (draft.tier === "immediate" && draft.missing.length === 0) {
              void runDraft(draft, draft.args);
            } else {
              setPending(draft);
            }
          },
          onNav: (to) => void navigate({ to }),
          onDone: () => setLoading(false),
          onError: (code, message) => {
            // "busy" is deliberately NOT treated as quota: the user's own
            // allowance is untouched, so the composer must stay enabled and
            // they can simply retry.
            if (code === "quota") setQuotaExceeded(true);
            if (code === "auth") setSignedOut(true);
            replaceLast(message);
            setLoading(false);
          },
        },
        controller.signal,
      );
    },
    [messages, loading, quotaExceeded, signedOut, lang, navigate, runDraft],
  );

  return {
    messages,
    loading,
    quotaExceeded,
    signedOut,
    pending,
    busyAction,
    send,
    confirmPending,
    cancelPending,
  };
}
