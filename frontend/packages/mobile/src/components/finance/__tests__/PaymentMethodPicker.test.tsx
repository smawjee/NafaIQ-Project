import { fireEvent, render } from "@testing-library/react-native";
import React from "react";

import { PaymentMethodPicker } from "@/components/finance/PaymentMethodPicker";
import { ThemeProvider } from "@/hooks/use-theme";

const OPTIONS = ["HBL Current", "Easypaisa", "Bank Alfalah · auto"];

function renderPicker(props: Partial<React.ComponentProps<typeof PaymentMethodPicker>> = {}) {
  const onChange = jest.fn();
  const onCreate = jest.fn();
  const utils = render(
    <ThemeProvider>
      <PaymentMethodPicker
        options={OPTIONS}
        value="HBL Current"
        onChange={onChange}
        onCreate={onCreate}
        {...props}
      />
    </ThemeProvider>,
  );
  return { ...utils, onChange, onCreate };
}

describe("PaymentMethodPicker", () => {
  it("lists every option as a chip and selects on tap", () => {
    const { getByText, onChange, onCreate } = renderPicker();
    for (const option of OPTIONS) expect(getByText(option)).toBeTruthy();

    fireEvent.press(getByText("Easypaisa"));
    expect(onChange).toHaveBeenCalledWith("Easypaisa");
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("creates a brand-new method through the + New flow", () => {
    const { getByText, getByPlaceholderText, onCreate } = renderPicker();

    fireEvent.press(getByText("+ New"));
    const input = getByPlaceholderText("e.g. Allied Bank Card, Cheque");
    fireEvent.changeText(input, "  Allied Bank Card ");
    fireEvent.press(getByText("Save"));

    expect(onCreate).toHaveBeenCalledWith("Allied Bank Card");
  });

  it("selects the existing option instead of creating a case-insensitive duplicate", () => {
    const { getByText, getByPlaceholderText, onChange, onCreate } = renderPicker();

    fireEvent.press(getByText("+ New"));
    fireEvent.changeText(getByPlaceholderText("e.g. Allied Bank Card, Cheque"), "easypaisa");
    fireEvent.press(getByText("Save"));

    expect(onCreate).not.toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith("Easypaisa");
  });

  it("relabels an option for display but still selects its stored value", () => {
    // "stock_trade" is a backend-generated source sharing this field with real
    // payment methods. It must read as "Stock trade" but round-trip untouched:
    // the finance summaries filter on source = 'stock_trade' to keep share
    // purchases out of expense totals.
    const { getByText, queryByText, onChange } = renderPicker({
      options: ["HBL Current", "stock_trade"],
      formatLabel: (v) => (v === "stock_trade" ? "Stock trade" : v),
    });

    expect(queryByText("stock_trade")).toBeNull();
    fireEvent.press(getByText("Stock trade"));

    expect(onChange).toHaveBeenCalledWith("stock_trade");
  });

  it("ignores saving an empty label", () => {
    const { getByText, onCreate, onChange } = renderPicker();
    fireEvent.press(getByText("+ New"));
    fireEvent.press(getByText("Save"));
    expect(onCreate).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });
});
