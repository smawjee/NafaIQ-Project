// Tests for the assistant SSE/JSON client: event dispatch across chunk-split
// frames, the pre-stream quota path, execute error surfacing, the RN multipart
// transcribe shape, and the Hermes-safe conversation id.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
jest.mock("expo/fetch", () => ({ fetch: jest.fn() }));

import { fetch as expoFetch } from "expo/fetch";

import {
  type AssistantHandlers,
  executeDraft,
  newConversationId,
  streamAssistant,
  transcribeAudio,
} from "@/lib/assistant/client";
import { supabase } from "@/lib/supabase";

const mExpoFetch = expoFetch as unknown as jest.Mock;
const mGetSession = supabase.auth.getSession as jest.Mock;

const signIn = () =>
  mGetSession.mockResolvedValue({ data: { session: { access_token: "jwt" } } });

function handlers(): AssistantHandlers & Record<string, jest.Mock> {
  return {
    onToken: jest.fn(),
    onTool: jest.fn(),
    onDraft: jest.fn(),
    onNav: jest.fn(),
    onDone: jest.fn(),
    onError: jest.fn(),
  };
}

function streamFrom(chunks: string[]) {
  let i = 0;
  return {
    status: 200,
    ok: true,
    body: {
      getReader: () => ({
        read: jest.fn().mockImplementation(() =>
          i < chunks.length
            ? Promise.resolve({ done: false, value: new TextEncoder().encode(chunks[i++]) })
            : Promise.resolve({ done: true, value: undefined }),
        ),
      }),
    },
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = jest.fn();
});

describe("newConversationId", () => {
  it("matches the backend's conversation_id contract", () => {
    for (let i = 0; i < 20; i++) {
      expect(newConversationId()).toMatch(/^[A-Za-z0-9-]{8,64}$/);
    }
  });
});

describe("streamAssistant", () => {
  it("dispatches every event type, including frames split across chunks", async () => {
    signIn();
    mExpoFetch.mockResolvedValueOnce(
      streamFrom([
        'data: {"type":"token","text":"Hi"}\n\ndata: {"type":"tool","name":"get_bills"}\n\n',
        'data: {"type":"draft","action":"add_transaction","tier":"confirm","args":{"amount":1200},"missing":["merchant"],"invalidate":["finance-transactions"]}\n\ndata: {"type":"na',
        'v","to":"/finance"}\n\ndata: {"type":"done","usage":{"used":3,"limit":40}}\n\n',
      ]),
    );

    const h = handlers();
    await streamAssistant(
      { lang: "en", messages: [{ role: "user", content: "hi" }], conversation_id: "abc-12345" },
      h,
    );

    expect(h.onToken).toHaveBeenCalledWith("Hi");
    expect(h.onTool).toHaveBeenCalledWith("get_bills");
    expect(h.onDraft).toHaveBeenCalledWith(
      expect.objectContaining({ action: "add_transaction", tier: "confirm", missing: ["merchant"] }),
    );
    expect(h.onNav).toHaveBeenCalledWith("/finance");
    expect(h.onDone).toHaveBeenCalledWith({ used: 3, limit: 40 });
    expect(h.onError).not.toHaveBeenCalled();
  });

  it("maps HTTP 429 to a quota error before streaming", async () => {
    signIn();
    mExpoFetch.mockResolvedValueOnce({ status: 429, ok: false });
    const h = handlers();
    await streamAssistant({ lang: "en", messages: [{ role: "user", content: "x" }] }, h);
    expect(h.onError).toHaveBeenCalledWith("quota", expect.any(String));
  });

  it("reports auth without fetching when signed out", async () => {
    mGetSession.mockResolvedValueOnce({ data: { session: null } });
    const h = handlers();
    await streamAssistant({ lang: "en", messages: [{ role: "user", content: "x" }] }, h);
    expect(h.onError).toHaveBeenCalledWith("auth", expect.any(String));
    expect(mExpoFetch).not.toHaveBeenCalled();
  });

  it("forwards in-stream busy errors with their code", async () => {
    signIn();
    mExpoFetch.mockResolvedValueOnce(
      streamFrom(['data: {"type":"error","code":"busy","message":"One moment","retryAfter":20}\n\n']),
    );
    const h = handlers();
    await streamAssistant({ lang: "en", messages: [{ role: "user", content: "x" }] }, h);
    expect(h.onError).toHaveBeenCalledWith("busy", "One moment");
  });
});

describe("executeDraft", () => {
  it("surfaces the server's detail message verbatim on failure", async () => {
    signIn();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: "Insufficient shares to sell" }),
    });
    await expect(executeDraft("record_trade", { symbol: "HBL" })).rejects.toThrow(
      "Insufficient shares to sell",
    );
  });

  it("returns the execute result and sends the conversation id", async () => {
    signIn();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({ ok: true, action: "add_to_watchlist", entity: {}, invalidate: ["watchlist"] }),
    });
    const result = await executeDraft("add_to_watchlist", { symbol: "MEBL" }, "conv-12345");
    expect(result.invalidate).toEqual(["watchlist"]);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      action: "add_to_watchlist",
      args: { symbol: "MEBL" },
      conversation_id: "conv-12345",
    });
  });
});

describe("transcribeAudio", () => {
  it("posts RN multipart FormData without a manual Content-Type", async () => {
    signIn();
    // RN's FormData keeps {uri,name,type} parts verbatim; the test env's
    // whatwg FormData stringifies them, so record appends with a fake.
    class RecordingFormData {
      parts: [string, unknown][] = [];
      append(key: string, value: unknown) {
        this.parts.push([key, value]);
      }
    }
    const realFormData = global.FormData;
    global.FormData = RecordingFormData as unknown as typeof FormData;
    try {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ text: " add 500 for fuel " }),
      });

      const text = await transcribeAudio("file:///tmp/rec.m4a", "ur");
      expect(text).toBe(" add 500 for fuel ");

      const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
      expect(url).toContain("/api/assistant/transcribe");
      // The boundary must come from fetch itself — a manual Content-Type breaks it.
      expect(init.headers["Content-Type"]).toBeUndefined();
      expect(init.headers.Authorization).toBe("Bearer jwt");
      const form = init.body as unknown as RecordingFormData;
      expect(form.parts).toEqual([
        ["file", { uri: "file:///tmp/rec.m4a", name: "command.m4a", type: "audio/m4a" }],
        ["lang", "ur"],
      ]);
    } finally {
      global.FormData = realFormData;
    }
  });
});
