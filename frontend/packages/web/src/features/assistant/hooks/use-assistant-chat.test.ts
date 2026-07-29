import { describe, expect, it } from "vitest";
import type { ActionDraft } from "@/lib/assistant/client";
import { type AssistantMsg, buildOutgoingMessages, draftStatusText } from "./use-assistant-chat";

const t = (value: string) => value;

function draft(overrides: Partial<ActionDraft>): ActionDraft {
  return {
    type: "draft",
    action: "add_transaction",
    tier: "confirm",
    args: {},
    missing: [],
    invalidate: [],
    ...overrides,
  };
}

describe("draftStatusText", () => {
  it("explains missing-field cards instead of leaving an empty assistant bubble", () => {
    expect(draftStatusText(draft({ missing: ["amount"] }), t)).toBe(
      "Please fill the highlighted details.",
    );
  });

  it("explains confirm cards before saving", () => {
    expect(draftStatusText(draft({ tier: "confirm" }), t)).toBe(
      "Please review this before I save it.",
    );
  });

  it("explains immediate actions while execution runs", () => {
    expect(draftStatusText(draft({ tier: "immediate" }), t)).toBe("Working on that now.");
  });
});

describe("buildOutgoingMessages", () => {
  const greeting: AssistantMsg = { role: "assistant", content: "Hi! I can help." };

  it("drops the leading UI greeting", () => {
    expect(buildOutgoingMessages([greeting, { role: "user", content: "hi" }])).toEqual([
      { role: "user", content: "hi" },
    ]);
  });

  it("keeps an assistant reply that is not the greeting", () => {
    const history: AssistantMsg[] = [
      greeting,
      { role: "user", content: "whats the price of OGDC stock?" },
      { role: "assistant", content: "OGDC is at 250 PKR." },
      { role: "user", content: "thanks" },
    ];
    expect(buildOutgoingMessages(history)).toEqual(history.slice(1));
  });

  it("filters empty assistant bubbles so one token-less turn cannot 422 every later request", () => {
    // Regression: a nav-only answer streams zero tokens, leaving "" in state.
    // The API requires content min_length=1, so re-sending it failed the whole
    // conversation permanently with HTTP 422.
    const history: AssistantMsg[] = [
      greeting,
      { role: "user", content: "take me to my portfolio" },
      { role: "assistant", content: "" },
      { role: "user", content: "hi" },
    ];
    expect(buildOutgoingMessages(history)).toEqual([
      { role: "user", content: "take me to my portfolio" },
      { role: "user", content: "hi" },
    ]);
  });

  it("treats whitespace-only bubbles as empty", () => {
    expect(
      buildOutgoingMessages([
        { role: "user", content: "hello" },
        { role: "assistant", content: "   " },
        { role: "user", content: "anyone?" },
      ]),
    ).toEqual([
      { role: "user", content: "hello" },
      { role: "user", content: "anyone?" },
    ]);
  });

  it("caps the history at the last 12 messages", () => {
    const long: AssistantMsg[] = Array.from({ length: 30 }, (_, i) => ({
      role: i % 2 === 0 ? ("user" as const) : ("assistant" as const),
      content: `turn ${i}`,
    }));
    const out = buildOutgoingMessages(long);
    expect(out).toHaveLength(12);
    expect(out[out.length - 1]).toEqual(long[29]);
  });
});
