// Tests for the AI tutor SSE client: the pure parser, the not-signed-in path,
// and a streamed happy-path with expo/fetch mocked to yield SSE bytes.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
jest.mock("expo/fetch", () => ({ fetch: jest.fn() }));

import { fetch as expoFetch } from "expo/fetch";

import { parseSseBuffer, streamTutor } from "@/lib/ai/tutor-client";
import { supabase } from "@/lib/supabase";

const mExpoFetch = expoFetch as unknown as jest.Mock;
const mGetSession = supabase.auth.getSession as jest.Mock;

beforeEach(() => jest.clearAllMocks());

describe("parseSseBuffer", () => {
  it("extracts complete data events and returns the unterminated tail", () => {
    const buf = 'data: {"type":"token","text":"Hi"}\n\ndata: {"type":"token","text":"!"}\n\ndata: {"type":"do';
    const { events, rest } = parseSseBuffer(buf);
    expect(events).toEqual([
      { type: "token", text: "Hi" },
      { type: "token", text: "!" },
    ]);
    expect(rest).toBe('data: {"type":"do');
  });

  it("tolerates keep-alive / malformed lines without throwing", () => {
    const buf = ": keep-alive\n\ndata: not-json\n\ndata: {\"type\":\"done\",\"usage\":{\"used\":1,\"limit\":10}}\n\n";
    const { events } = parseSseBuffer(buf);
    expect(events).toEqual([{ type: "done", usage: { used: 1, limit: 10 } }]);
  });
});

describe("streamTutor", () => {
  it("reports an auth error when there is no session", async () => {
    mGetSession.mockResolvedValueOnce({ data: { session: null } });
    const onError = jest.fn();
    await streamTutor(
      { lessonTitle: "x", lang: "en", messages: [] },
      { onToken: jest.fn(), onDone: jest.fn(), onError },
    );
    expect(onError).toHaveBeenCalledWith("auth", expect.any(String));
    expect(mExpoFetch).not.toHaveBeenCalled();
  });

  it("streams tokens then done when signed in", async () => {
    mGetSession.mockResolvedValueOnce({ data: { session: { access_token: "jwt" } } });
    const chunks = [
      'data: {"type":"token","text":"Hel"}\n\n',
      'data: {"type":"token","text":"lo"}\n\ndata: {"type":"done","usage":{"used":2,"limit":50}}\n\n',
    ];
    let i = 0;
    const reader = {
      read: jest.fn().mockImplementation(() =>
        i < chunks.length
          ? Promise.resolve({ done: false, value: new TextEncoder().encode(chunks[i++]) })
          : Promise.resolve({ done: true, value: undefined }),
      ),
    };
    mExpoFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      body: { getReader: () => reader },
    });

    const onToken = jest.fn();
    const onDone = jest.fn();
    await streamTutor(
      { lessonTitle: "x", lang: "en", messages: [{ role: "user", content: "hi" }] },
      { onToken, onDone, onError: jest.fn() },
    );

    expect(mExpoFetch).toHaveBeenCalledWith(expect.stringContaining("/api/ai/tutor"), expect.objectContaining({ method: "POST" }));
    expect(onToken.mock.calls.map((c) => c[0]).join("")).toBe("Hello");
    expect(onDone).toHaveBeenCalledWith({ used: 2, limit: 50 });
  });
});
