import { describe, expect, it } from "vitest";
import type { ActionDraft } from "@/lib/assistant/client";
import { draftStatusText } from "./use-assistant-chat";

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
