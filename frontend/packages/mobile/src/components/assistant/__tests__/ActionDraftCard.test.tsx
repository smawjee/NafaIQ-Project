import { fireEvent, render } from "@testing-library/react-native";
import React from "react";

import { ActionDraftCard } from "@/components/assistant/ActionDraftCard";
import { ThemeProvider } from "@/hooks/use-theme";
import type { ActionDraft } from "@/lib/assistant/client";

function draft(partial: Partial<ActionDraft>): ActionDraft {
  return {
    type: "draft",
    action: "add_transaction",
    tier: "confirm",
    args: {},
    missing: [],
    invalidate: [],
    ...partial,
  };
}

function renderCard(d: ActionDraft, busy = false) {
  const onConfirm = jest.fn();
  const onCancel = jest.fn();
  const utils = render(
    <ThemeProvider>
      <ActionDraftCard draft={d} busy={busy} onConfirm={onConfirm} onCancel={onCancel} />
    </ThemeProvider>,
  );
  return { ...utils, onConfirm, onCancel };
}

describe("ActionDraftCard", () => {
  it("renders the per-action fields seeded from the draft args", () => {
    const { getByText, getByDisplayValue } = renderCard(
      draft({ args: { merchant: "Foodpanda", amount: 1200, category: "Food & Dining" } }),
    );
    expect(getByText("Add transaction")).toBeTruthy();
    expect(getByDisplayValue("Foodpanda")).toBeTruthy();
    expect(getByDisplayValue("1200")).toBeTruthy();
  });

  it("blocks Confirm while required fields are missing, then submits with coerced numbers", () => {
    const { getByText, getByLabelText, onConfirm } = renderCard(
      draft({ args: { merchant: "Careem" }, missing: ["amount"] }),
    );
    expect(getByText(/Still needed/)).toBeTruthy();

    fireEvent.press(getByText("Confirm"));
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.changeText(getByLabelText("Amount (PKR) *"), "450");
    fireEvent.press(getByText("Confirm"));
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ merchant: "Careem", amount: 450 }),
    );
  });

  it("re-attaches unrendered draft args on submit", () => {
    const { getByText, onConfirm } = renderCard(
      draft({
        args: {
          merchant: "Daraz",
          amount: 900,
          portfolio_id: 7,
          transaction_date: "2026-07-23",
        },
      }),
    );
    fireEvent.press(getByText("Confirm"));
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ portfolio_id: 7, transaction_date: "2026-07-23" }),
    );
  });

  it("widens select options so an off-list source stays selectable", () => {
    const { getByText, onConfirm } = renderCard(
      draft({ args: { merchant: "Chai Wala", amount: 50, source: "Pocket Money" } }),
    );
    // The free-text value is a chip, not silently dropped.
    expect(getByText("Pocket Money")).toBeTruthy();
    fireEvent.press(getByText("Confirm"));
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ source: "Pocket Money" }));
  });

  it("cancel notifies and busy disables both buttons", () => {
    const first = renderCard(draft({ args: { symbol: "HBL" }, action: "add_to_watchlist" }));
    fireEvent.press(first.getByText("Cancel"));
    expect(first.onCancel).toHaveBeenCalled();

    const busy = renderCard(draft({ args: { symbol: "HBL" }, action: "add_to_watchlist" }), true);
    fireEvent.press(busy.getByText("Cancel"));
    expect(busy.onCancel).not.toHaveBeenCalled();
  });
});
