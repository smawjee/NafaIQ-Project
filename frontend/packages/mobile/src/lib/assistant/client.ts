// SSE + JSON client for the NafaIQ Assistant (POST /api/assistant/*). Mobile
// twin of web's src/lib/assistant/client.ts — same event contract and endpoint
// surface, adapted to Expo:
//   - `expo/fetch` for the chat stream (RN's global fetch cannot stream);
//   - `transcribeAudio` takes a recorded file URI (RN FormData), not a Blob;
//   - `newConversationId()` instead of crypto.randomUUID (absent under Hermes).
//
// The SSE framing is byte-for-byte identical to the tutor's, so parseSseBuffer
// is IMPORTED from the tutor client rather than copied — two parsers for one
// wire format would drift.

import { fetch as expoFetch } from "expo/fetch";

import { parseSseBuffer } from "@/lib/ai/tutor-client";
import { apiUrl } from "@/lib/api";
import { supabase } from "@/lib/supabase";

/** A write the user must see before it happens. Never executed by the model. */
export interface ActionDraft {
  type: "draft";
  action: string;
  /** "confirm" -> editable card + explicit OK. "immediate" -> run now. */
  tier: "confirm" | "immediate";
  args: Record<string, unknown>;
  /** Required fields still unfilled; the agent will have asked about these. */
  missing: string[];
  /** Server-side (web-flavored) query keys — translate via mappings.ts. */
  invalidate: string[];
}

export type AssistantEvent =
  | { type: "token"; text: string }
  | { type: "tool"; name: string }
  | ActionDraft
  | { type: "nav"; to: string }
  | { type: "done"; usage: { used: number; limit: number | null } }
  // "busy" = the AI provider is throttling us, which is retryable and must not
  // read as a breakage. "quota" = the user's own daily allowance, which is not.
  | {
      type: "error";
      code: "quota" | "provider" | "auth" | "busy";
      message: string;
      retryAfter?: number;
    };

export interface AssistantHandlers {
  onToken(text: string): void;
  onTool(name: string): void;
  onDraft(draft: ActionDraft): void;
  onNav(to: string): void;
  onDone(usage: { used: number; limit: number | null }): void;
  onError(code: "quota" | "provider" | "auth" | "busy", message: string): void;
}

export interface AssistantPayload {
  lang: "en" | "ur";
  messages: { role: "user" | "assistant"; content: string }[];
  /** Client-generated per chat session; groups the conversation's traces in
   *  Langfuse. Optional — observability only, never used for logic. */
  conversation_id?: string;
}

/** Hermes has no crypto.randomUUID; the backend only requires
 * ^[A-Za-z0-9-]+$ of length 8-64, and the id is observability-only. */
export function newConversationId(): string {
  const rand = () => Math.random().toString(36).slice(2, 10);
  return `${Date.now().toString(36)}-${rand()}-${rand()}`;
}

async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function streamAssistant(
  payload: AssistantPayload,
  handlers: AssistantHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = await getAccessToken();
  if (!token) {
    handlers.onError("auth", "Not signed in");
    return;
  }
  let res: Response;
  try {
    res = (await expoFetch(apiUrl("/api/assistant/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
      signal,
    })) as unknown as Response;
  } catch (e) {
    if (signal?.aborted) return; // user left the screen — not an error
    handlers.onError("provider", String(e));
    return;
  }
  if (res.status === 401) {
    handlers.onError("auth", "Session expired");
    return;
  }
  if (res.status === 429) {
    handlers.onError("quota", "Daily assistant limit reached");
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError("provider", `HTTP ${res.status}`);
    return;
  }

  const reader = (res.body as ReadableStream<Uint8Array>).getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseBuffer<AssistantEvent>(buffer);
      buffer = parsed.rest;
      for (const ev of parsed.events) {
        switch (ev.type) {
          case "token":
            handlers.onToken(ev.text);
            break;
          case "tool":
            handlers.onTool(ev.name);
            break;
          case "draft":
            handlers.onDraft(ev);
            break;
          case "nav":
            handlers.onNav(ev.to);
            break;
          case "done":
            handlers.onDone(ev.usage);
            break;
          case "error":
            handlers.onError(ev.code, ev.message);
            break;
        }
      }
    }
  } catch (e) {
    if (!signal?.aborted) handlers.onError("provider", String(e));
  }
}

export interface ExecuteResult {
  ok: boolean;
  action: string;
  entity: unknown;
  invalidate: string[];
}

/** Perform a confirmed draft. The server re-validates every field. */
export async function executeDraft(
  action: string,
  args: Record<string, unknown>,
  conversationId?: string,
): Promise<ExecuteResult> {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(apiUrl("/api/assistant/execute"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ action, args, conversation_id: conversationId }),
  });
  if (!res.ok) {
    // The domain services return actionable messages ("Insufficient shares to
    // sell"); surface them verbatim rather than a generic failure, so the user
    // can fix the card and retry.
    const detail = await res
      .json()
      .then((b) => (typeof b?.detail === "string" ? b.detail : null))
      .catch(() => null);
    throw new Error(detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<ExecuteResult>;
}

/** Transcribe a recorded clip (by file URI). Returns text for the composer,
 * unsent — the user confirms what was heard before anything acts on it. */
export async function transcribeAudio(uri: string, lang: "en" | "ur"): Promise<string> {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const form = new FormData();
  // RN FormData takes {uri, name, type}. The extension matters: the backend
  // forwards the filename to Whisper, which uses it to pick a demuxer.
  form.append("file", { uri, name: "command.m4a", type: "audio/m4a" } as unknown as Blob);
  form.append("lang", lang);
  const res = await fetch(apiUrl("/api/assistant/transcribe"), {
    method: "POST",
    // No Content-Type: fetch must set the multipart boundary itself.
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (typeof b?.detail === "string" ? b.detail : null))
      .catch(() => null);
    throw new Error(detail ?? `Transcription failed (${res.status})`);
  }
  const data = (await res.json()) as { text: string };
  return data.text;
}
