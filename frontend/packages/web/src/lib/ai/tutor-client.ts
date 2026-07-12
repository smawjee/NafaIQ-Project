// SSE client for the FastAPI AI tutor (POST /api/ai/tutor).
// Auth mirrors psx/client.ts user* helpers: Supabase session JWT as bearer.

import { apiUrl } from "@/lib/api";

export type TutorEvent =
  | { type: "token"; text: string }
  | { type: "done"; usage: { used: number; limit: number | null } }
  | { type: "error"; code: "quota" | "provider" | "auth"; message: string };

export interface TutorPayload {
  lessonTitle: string;
  lessonContext?: string;
  lang: "en" | "ur";
  messages: { role: "user" | "assistant"; content: string }[];
}

export interface TutorHandlers {
  onToken(text: string): void;
  onDone(usage: { used: number; limit: number | null }): void;
  onError(code: "quota" | "provider" | "auth", message: string): void;
}

/** Pure SSE parser: extracts complete `data: {json}` blocks, returns the
 * unterminated tail as `rest` for the next chunk. Exported for tests. */
export function parseSseBuffer(buffer: string): { events: TutorEvent[]; rest: string } {
  const events: TutorEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    for (const line of block.split("\n")) {
      if (!line.startsWith("data:")) continue;
      try {
        events.push(JSON.parse(line.slice(5).trim()) as TutorEvent);
      } catch {
        // tolerate keep-alives / malformed lines
      }
    }
  }
  return { events, rest };
}

async function getAccessToken(): Promise<string | null> {
  const { supabase } = await import("@/integrations/supabase/client");
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function streamTutor(
  payload: TutorPayload,
  handlers: TutorHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = await getAccessToken();
  if (!token) {
    handlers.onError("auth", "Not signed in");
    return;
  }
  let res: Response;
  try {
    res = await fetch(apiUrl("/api/ai/tutor"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (e) {
    if (signal?.aborted) return; // user closed the panel — not an error
    handlers.onError("provider", String(e));
    return;
  }
  if (res.status === 401) {
    handlers.onError("auth", "Session expired");
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError("provider", `HTTP ${res.status}`);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseBuffer(buffer);
      buffer = parsed.rest;
      for (const ev of parsed.events) {
        if (ev.type === "token") handlers.onToken(ev.text);
        else if (ev.type === "done") handlers.onDone(ev.usage);
        else handlers.onError(ev.code, ev.message);
      }
    }
  } catch (e) {
    if (!signal?.aborted) handlers.onError("provider", String(e));
  }
}

async function authedGet<T>(path: string): Promise<T> {
  const token = await getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(apiUrl(path), { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchTutorHistory(
  limit = 12,
): Promise<{ role: "user" | "assistant"; content: string }[]> {
  return authedGet(`/api/ai/tutor/history?limit=${limit}`);
}

export function fetchTutorUsage(): Promise<{
  used: number;
  limit: number | null;
  remaining: number | null;
}> {
  return authedGet("/api/ai/tutor/usage");
}
