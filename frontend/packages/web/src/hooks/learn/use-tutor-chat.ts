// Shared AI-tutor chat state for HubChatPanel and lesson ChatPanel.
// Streams tokens into the last assistant bubble; handles quota, auth, abort.

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTutorHistory, streamTutor } from "@/lib/ai/tutor-client";
import { useLang } from "@/hooks/use-lang";
import { askStudioTutor } from "@/lib/learn/studio-client";

export interface TutorChatMsg {
  role: "user" | "assistant";
  content: string;
}

export interface UseTutorChatOptions {
  lessonTitle: string;
  lessonContext?: string;
  greeting: string;
  /** Load recent server-side history on mount (hub panel). */
  hydrate?: boolean;
  /** Generated lessons use their private, source-grounded Studio endpoint. */
  projectId?: string;
}

export function useTutorChat(opts: UseTutorChatOptions) {
  const { lang } = useLang();
  const [messages, setMessages] = useState<TutorChatMsg[]>([
    { role: "assistant", content: opts.greeting },
  ]);
  const [loading, setLoading] = useState(false);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Refresh the greeting when the language toggles (pre-existing behavior).
  useEffect(() => {
    setMessages((current) =>
      current.length === 1 && current[0]?.role === "assistant"
        ? [{ role: "assistant", content: opts.greeting }]
        : current,
    );
  }, [opts.greeting]);

  // Signed-in check (+ optional history hydration) on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { supabase } = await import("@/integrations/supabase/client");
      const { data } = await supabase.auth.getSession();
      if (cancelled) return;
      if (!data.session) {
        setSignedOut(true);
        return;
      }
      if (opts.hydrate) {
        try {
          const history = await fetchTutorHistory(12);
          if (!cancelled && history.length > 0) {
            // Functional update so hydration never clobbers an exchange the
            // user started while history was loading.
            setMessages((current) =>
              current.length > 1
                ? current
                : [
                    { role: "assistant", content: opts.greeting },
                    ...history.map((h) => ({ role: h.role, content: h.content })),
                  ],
            );
          }
        } catch {
          // hydration is best-effort; keep the greeting
        }
      }
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading || quotaExceeded || signedOut) return;
      setLoading(true);
      // Derive from current state; updater stays pure.
      const history: TutorChatMsg[] = [...messages, { role: "user", content: trimmed }];
      // Empty assistant bubble that streaming tokens append into.
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

      if (opts.projectId) {
        void askStudioTutor(opts.projectId, {
          message: trimmed,
          history: history.filter((m, i) => !(i === 0 && m.role === "assistant")).slice(-6, -1),
          lang,
        })
          .then((result) => replaceLast(result.answer ?? "This lesson does not cover that question."))
          .catch((error: unknown) => {
            const message = error instanceof Error ? error.message : "";
            if (/\b429\b/.test(message)) setQuotaExceeded(true);
            replaceLast(/\b429\b/.test(message) ? "Daily LearnHub AI limit reached." : "The lesson tutor is unavailable right now.");
          })
          .finally(() => setLoading(false));
        return;
      }

      void streamTutor(
        {
          lessonTitle: opts.lessonTitle,
          lessonContext: opts.lessonContext,
          lang,
          // Drop the leading UI greeting; send the last 12 real turns.
          messages: history.filter((m, i) => !(i === 0 && m.role === "assistant")).slice(-12),
        },
        {
          onToken: appendToLast,
          onDone: () => setLoading(false),
          onError: (code, message) => {
            if (code === "quota") {
              setQuotaExceeded(true);
              replaceLast(message);
            } else if (code === "auth") {
              setSignedOut(true);
              replaceLast(message);
            } else {
              replaceLast(message);
            }
            setLoading(false);
          },
        },
        controller.signal,
      );
    },
    [messages, loading, quotaExceeded, signedOut, lang, opts.lessonTitle, opts.lessonContext, opts.projectId],
  );

  return { messages, loading, quotaExceeded, signedOut, send };
}
