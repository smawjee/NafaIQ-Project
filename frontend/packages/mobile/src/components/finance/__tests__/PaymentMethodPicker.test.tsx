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

  it("ignores saving an empty label", () => {
    const { getByText, onCreate, onChange } = renderPicker();
    fireEvent.press(getByText("+ New"));
    fireEvent.press(getByText("Save"));
    expect(onCreate).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });
});
