// Settings -> change password.
//
// The load-bearing behaviour is the current-password re-check: without it an
// unattended unlocked phone is enough to take the account over permanently,
// because a session is a weaker thing to trust than the password itself. Each
// guard below must block BEFORE setNewPassword is reached.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { fireEvent, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";
import React from "react";

jest.mock("@/lib/auth/recovery", () => ({
  verifyCurrentPassword: jest.fn(),
  setNewPassword: jest.fn(),
}));

import { ChangePasswordCard } from "@/components/settings/ChangePasswordCard";
import { setNewPassword, verifyCurrentPassword } from "@/lib/auth/recovery";
import { renderWithProviders } from "@/test-utils";

const mVerify = verifyCurrentPassword as jest.Mock;
const mSet = setNewPassword as jest.Mock;

const CURRENT = "OldPass!2026";
const NEXT = "BrandNew!2026";

let alertSpy: jest.SpyInstance;

beforeEach(() => {
  jest.clearAllMocks();
  mVerify.mockResolvedValue({ error: null });
  mSet.mockResolvedValue({ error: null });
  alertSpy = jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

afterEach(() => alertSpy.mockRestore());

function renderCard() {
  return renderWithProviders(<ChangePasswordCard email="user@example.com" />);
}

/** Fill the three fields and submit. */
function submit(
  utils: ReturnType<typeof renderCard>,
  { current = CURRENT, next = NEXT, confirm = NEXT } = {},
) {
  fireEvent.changeText(utils.getByLabelText("Current password"), current);
  fireEvent.changeText(utils.getByLabelText("New password"), next);
  fireEvent.changeText(utils.getByLabelText("Confirm new password"), confirm);
  fireEvent.press(utils.getByLabelText("Update password"));
}

/** The message text of every Alert.alert call, flattened. */
function alerts(): string {
  return alertSpy.mock.calls.map((c) => c.join(" ")).join(" | ");
}

it("renders the three fields", () => {
  const utils = renderCard();
  expect(utils.getByLabelText("Current password")).toBeTruthy();
  expect(utils.getByLabelText("New password")).toBeTruthy();
  expect(utils.getByLabelText("Confirm new password")).toBeTruthy();
});

it("verifies the current password before changing anything", async () => {
  const utils = renderCard();
  submit(utils);

  await waitFor(() => expect(mSet).toHaveBeenCalledWith(NEXT));
  expect(mVerify).toHaveBeenCalledWith("user@example.com", CURRENT);
  // Order matters: the check must precede the write, not follow it.
  expect(mVerify.mock.invocationCallOrder[0]).toBeLessThan(mSet.mock.invocationCallOrder[0]);
});

it("refuses to write when the current password is wrong", async () => {
  mVerify.mockResolvedValue({ error: "Current password is incorrect." });
  const utils = renderCard();

  submit(utils);

  await waitFor(() => expect(alerts()).toMatch(/current password is incorrect/i));
  expect(mSet).not.toHaveBeenCalled();
});

it("blocks a mismatched confirmation without touching the server", async () => {
  const utils = renderCard();
  submit(utils, { confirm: "SomethingElse!1" });

  await waitFor(() => expect(alerts()).toMatch(/don't match/i));
  expect(mVerify).not.toHaveBeenCalled();
  expect(mSet).not.toHaveBeenCalled();
});

it("blocks a too-short new password", async () => {
  const utils = renderCard();
  submit(utils, { next: "Ab1!", confirm: "Ab1!" });

  await waitFor(() => expect(alerts()).toMatch(/at least 8 characters/i));
  expect(mSet).not.toHaveBeenCalled();
});

it("blocks reusing the current password", async () => {
  const utils = renderCard();
  submit(utils, { next: CURRENT, confirm: CURRENT });

  await waitFor(() => expect(alerts()).toMatch(/must be different/i));
  expect(mSet).not.toHaveBeenCalled();
});

it("clears the fields and confirms once the password is changed", async () => {
  const utils = renderCard();
  submit(utils);

  await waitFor(() => expect(alerts()).toMatch(/password updated/i));
  expect(utils.getByLabelText("Current password").props.value).toBe("");
  expect(utils.getByLabelText("New password").props.value).toBe("");
  expect(utils.getByLabelText("Confirm new password").props.value).toBe("");
});

it("surfaces a failed write instead of claiming success", async () => {
  mSet.mockResolvedValue({ error: "Password is too weak" });
  const utils = renderCard();

  submit(utils);

  await waitFor(() => expect(alerts()).toMatch(/too weak/i));
  expect(alerts()).not.toMatch(/password updated/i);
});
