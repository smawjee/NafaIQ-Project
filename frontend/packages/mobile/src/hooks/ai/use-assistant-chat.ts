// Chat + action state for the NafaIQ Assistant screen. Port of the web
// hook (web/src/features/assistant/hooks/use-assistant-chat.ts) with four
// mobile substitutions: newConversationId() for crypto.randomUUID (Hermes),
// expo-router navigation via mapNavRoute, invalidation via mapInvalidateKeys
// (server keys are web-flavored), and an onToast callback instead of sonner —
// the screen owns its glass toast pill.
//
// The tiering rule lives here because it is a UI decision:
//   tier "confirm"   -> park the draft; a card renders and the user approves.
//   tier "immediate" -> execute on arrival and toast the result.
// A draft with `missing` fields is NEVER auto-executed regardless of tier —
// the agent is still collecting information.

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";

import {
  type ActionDraft,
  executeDraft,
  newConversationId,
  streamAssistant,
} from "@/lib/assistant/client";
import { mapInvalidateKeys, mapNavRoute } from "@/lib/assistant/mappings";
import { supabase } from "@/lib/supabase";
import { useLang } from "@/hooks/use-lang";

export interface AssistantMsg {
  role: "user" | "assistant";
  content: string;
}

export function draftStatusText(draft: ActionDraft, t: (value: string) => string): string {
  if (draft.missing.length > 0) return t("Please fill the highlighted details.");
  if (draft.tier === "confirm") return t("Please review this before I save it.");
  return t("Working on that now.");
}

export function useAssistantChat(
  greeting: string,
  options?: { onToast?: (message: string, kind: "success" | "error") => void },
) {
  const { lang, t } = useLang();
  const qc = useQueryClient();
  const router = useRouter();
  const onToast = options?.onToast;

  const [messages, setMessages] = useState<AssistantMsg[]>([
    { role: "assistant", content: greeting },
  ]);
  const [loading, setLoading] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const [pending, setPending] = useState<ActionDraft | null>(null);
  const [busyAction, setBusyAction] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // One id per hook mount = one Langfuse session per conversation.
  const conversationIdRef = useRef<string>(newConversationId());

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
      const { data } = await supabase.auth.getSession();
      if (!cancelled && !data.session) setSignedOut(true);
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, []);

  const invalidate = useCallback(
    (serverKeys: string[]) => {
      for (const queryKey of mapInvalidateKeys(serverKeys)) {
        void qc.invalidateQueries({ queryKey });
      }
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
        onToast?.(t("Done"), "success");
        setPending(null);
        return true;
      } catch (e) {
        // Domain errors are actionable ("Savings goals limit reached for Free
        // plan"), so show them and leave the card open for editing.
        onToast?.(e instanceof Error ? e.message : t("Something went wrong"), "error");
        return false;
      } finally {
        setBusyAction(false);
      }
    },
    [invalidate, onToast, t],
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
          onNav: (to) => {
            const href = mapNavRoute(to);
            // Unmapped destinations are dropped, like the server drops
            // unresolved ones — never a crash on a web-only route.
            if (href) router.push(href as never);
          },
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
    [messages, loading, quotaExceeded, signedOut, lang, router, runDraft, t],
  );

  const abort = useCallback(() => abortRef.current?.abort(), []);

  return {
    messages,
    loading,
    quotaExceeded,
    signedOut,
    pending,
    busyAction,
    send,
    abort,
    confirmPending,
    cancelPending,
  };
}
