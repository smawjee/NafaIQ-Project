import { afterEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL } from "@/lib/api";
import { streamAssistant, type ActionDraft, type AssistantEvent } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

function mockSessionToken(token: string | null) {
  vi.doMock("@/integrations/supabase/client", () => ({
    supabase: {
      auth: {
        getSession: async () => ({
          data: { session: token ? { access_token: token } : null },
        }),
      },
    },
  }));
}

function sseResponse(events: string[]): Response {
  return new Response(events.join(""), {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

function data(event: AssistantEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

describe("streamAssistant", () => {
  it("dispatches clean token, draft, nav, done, and error events", async () => {
    mockSessionToken("tok");
    const draft: ActionDraft = {
      type: "draft",
      action: "add_transaction",
      tier: "confirm",
      args: { merchant: "KFC", transaction_type: "expense" },
      missing: ["amount"],
      invalidate: ["finance-transactions"],
    };
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        data({ type: "token", text: "Please review this." }),
        data({ type: "tool", name: "get_bills" }),
        data(draft),
        data({ type: "nav", to: "/finance" }),
        data({ type: "done", usage: { used: 2, limit: 40 } }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    const seen: unknown[] = [];
    await streamAssistant(
      {
        lang: "en",
        messages: [{ role: "user", content: "add food" }],
        conversation_id: "c1",
      },
      {
        onToken: (text) => seen.push(["token", text]),
        onTool: (name) => seen.push(["tool", name]),
        onDraft: (d) => seen.push(["draft", d]),
        onNav: (to) => seen.push(["nav", to]),
        onDone: (usage) => seen.push(["done", usage]),
        onError: (code, message) => seen.push(["error", code, message]),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/assistant/chat`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: "Bearer tok" }),
      }),
    );
    expect(seen).toEqual([
      ["token", "Please review this."],
      ["tool", "get_bills"],
      ["draft", draft],
      ["nav", "/finance"],
      ["done", { used: 2, limit: 40 }],
    ]);
  });

  it("ignores malformed SSE frames and still renders later clean events", async () => {
    mockSessionToken("tok");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse(["data: {broken\n\n", data({ type: "token", text: "Clean answer" })]),
      ),
    );
    const tokens: string[] = [];

    await streamAssistant(
      { lang: "en", messages: [{ role: "user", content: "hi" }] },
      {
        onToken: (text) => tokens.push(text),
        onTool: () => undefined,
        onDraft: () => undefined,
        onNav: () => undefined,
        onDone: () => undefined,
        onError: () => undefined,
      },
    );

    expect(tokens).toEqual(["Clean answer"]);
  });

  it("reports auth locally when no session exists", async () => {
    mockSessionToken(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const errors: string[] = [];

    await streamAssistant(
      { lang: "en", messages: [{ role: "user", content: "hi" }] },
      {
        onToken: () => undefined,
        onTool: () => undefined,
        onDraft: () => undefined,
        onNav: () => undefined,
        onDone: () => undefined,
        onError: (code, message) => errors.push(`${code}:${message}`),
      },
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(errors).toEqual(["auth:Not signed in"]);
  });
});
