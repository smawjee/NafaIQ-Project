// Tests for the assistant chat state machine: draft tiering, mapped
// invalidation, mapped navigation, and the quota-vs-busy distinction.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react-native";
import React from "react";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({ useRouter: () => ({ push: mockPush }) }));
jest.mock("@/lib/assistant/client", () => ({
  streamAssistant: jest.fn(),
  executeDraft: jest.fn(),
  newConversationId: () => "test-conv-12345",
}));

import { type ActionDraft, executeDraft, streamAssistant } from "@/lib/assistant/client";
import { useAssistantChat } from "@/hooks/ai/use-assistant-chat";

const mStream = streamAssistant as jest.Mock;
const mExecute = executeDraft as jest.Mock;

function draft(partial: Partial<ActionDraft>): ActionDraft {
  return {
    type: "draft",
    action: "add_to_watchlist",
    tier: "immediate",
    args: { symbol: "MEBL" },
    missing: [],
    invalidate: ["watchlist"],
    ...partial,
  };
}

let qc: QueryClient;
function wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

function renderChat() {
  const onToast = jest.fn();
  const utils = renderHook(() => useAssistantChat("Hi!", { onToast }), { wrapper });
  return { ...utils, onToast };
}

beforeEach(() => {
  jest.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

describe("useAssistantChat", () => {
  it("auto-executes an immediate draft with no missing fields and invalidates MAPPED keys", async () => {
    mExecute.mockResolvedValue({
      ok: true,
      action: "add_to_watchlist",
      entity: {},
      invalidate: ["watchlist", "enriched-watchlist"],
    });
    mStream.mockImplementation(async (_payload, handlers) => {
      handlers.onDraft(draft({}));
      handlers.onDone({ used: 1, limit: 40 });
    });
    const spy = jest.spyOn(qc, "invalidateQueries");

    const { result, onToast } = renderChat();
    act(() => result.current.send("Add MEBL to my watchlist"));

    await waitFor(() => expect(mExecute).toHaveBeenCalled());
    expect(mExecute).toHaveBeenCalledWith("add_to_watchlist", { symbol: "MEBL" }, "test-conv-12345");
    await waitFor(() => expect(onToast).toHaveBeenCalledWith(expect.any(String), "success"));
    // Server keys are translated to mobile queryKey prefixes.
    expect(spy).toHaveBeenCalledWith({ queryKey: ["watchlist"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["enriched-watchlist"] });
    expect(result.current.pending).toBeNull();
  });

  it("parks a confirm-tier draft instead of executing", async () => {
    mStream.mockImplementation(async (_payload, handlers) => {
      handlers.onDraft(draft({ action: "add_transaction", tier: "confirm" }));
      handlers.onDone({ used: 1, limit: 40 });
    });

    const { result } = renderChat();
    act(() => result.current.send("add a transaction"));

    await waitFor(() => expect(result.current.pending?.action).toBe("add_transaction"));
    expect(mExecute).not.toHaveBeenCalled();
  });

  it("never auto-runs an immediate draft that has missing fields", async () => {
    mStream.mockImplementation(async (_payload, handlers) => {
      handlers.onDraft(draft({ missing: ["symbol"], args: {} }));
      handlers.onDone({ used: 1, limit: 40 });
    });

    const { result } = renderChat();
    act(() => result.current.send("add to watchlist"));

    await waitFor(() => expect(result.current.pending).not.toBeNull());
    expect(mExecute).not.toHaveBeenCalled();
  });

  it("pushes mapped nav routes and drops web-only ones", async () => {
    mStream.mockImplementation(async (_payload, handlers) => {
      handlers.onNav("/portfolio");
      handlers.onNav("/help");
      handlers.onDone({ used: 1, limit: 40 });
    });

    const { result } = renderChat();
    act(() => result.current.send("take me to my portfolio"));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/(tabs)/portfolio"));
    expect(mockPush).toHaveBeenCalledTimes(1); // "/help" dropped silently
  });

  it("quota disables further sends; busy does not", async () => {
    mStream.mockImplementationOnce(async (_payload, handlers) => {
      handlers.onError("busy", "One moment");
    });
    const { result } = renderChat();
    act(() => result.current.send("hello"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.quotaExceeded).toBe(false); // retryable

    mStream.mockImplementationOnce(async (_payload, handlers) => {
      handlers.onError("quota", "Daily assistant limit reached");
    });
    act(() => result.current.send("again"));
    await waitFor(() => expect(result.current.quotaExceeded).toBe(true));

    // Now sends are refused outright.
    act(() => result.current.send("one more"));
    expect(mStream).toHaveBeenCalledTimes(2);
  });

  it("sends the last 12 turns without the greeting", async () => {
    mStream.mockImplementation(async (_payload, handlers) => handlers.onDone({ used: 1, limit: 40 }));
    const { result } = renderChat();
    act(() => result.current.send("first question"));

    await waitFor(() => expect(mStream).toHaveBeenCalled());
    const payload = mStream.mock.calls[0][0];
    expect(payload.messages).toEqual([{ role: "user", content: "first question" }]);
    expect(payload.conversation_id).toBe("test-conv-12345");
  });
});
