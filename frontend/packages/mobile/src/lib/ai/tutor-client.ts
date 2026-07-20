// SSE client for the FastAPI AI tutor (POST /api/ai/tutor). Mobile twin of
// web's src/lib/ai/tutor-client.ts — same event contract + Supabase JWT bearer.
//
// RN's global fetch does NOT stream a response body, so we use `expo/fetch`
// (Expo SDK 54). Its Response.body is a real web ReadableStream, which we read
// with getReader() + TextDecoder and split on the SSE "\n\n" record boundary.
import { fetch as expoFetch } from "expo/fetch";

import { apiUrl, userGet } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export type TutorEvent =
  | { type: "token"; text: string }
  | { type: "meta"; [key: string]: unknown }
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
 * unterminated tail as `rest` for the next chunk. */
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
    res = (await expoFetch(apiUrl("/api/ai/tutor"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
      signal,
    })) as unknown as Response;
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
  const reader = (res.body as ReadableStream<Uint8Array>).getReader();
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
        else if (ev.type === "error") handlers.onError(ev.code, ev.message);
        // "meta" events carry no UI payload we render — ignore.
      }
    }
  } catch (e) {
    if (!signal?.aborted) handlers.onError("provider", String(e));
  }
}

export function fetchTutorHistory(
  limit = 12,
): Promise<{ role: "user" | "assistant"; content: string }[]> {
  return userGet(`/api/ai/tutor/history?limit=${limit}`);
}

export function fetchTutorUsage(): Promise<{
  used: number;
  limit: number | null;
  remaining: number | null;
}> {
  return userGet("/api/ai/tutor/usage");
}
