// ForgotPasswordCard — the three-step recovery flow.
//
// The first test is the important one: a failing request must STILL advance the
// user to the code step. The backend is deliberately silent about whether an
// address is registered, and surfacing a failure here would leak exactly what
// the silence protects.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import React from "react";

jest.mock("@/lib/auth/recovery", () => ({
  requestPasswordReset: jest.fn(),
  verifyRecoveryCode: jest.fn(),
  setNewPassword: jest.fn(),
}));

const mockSetRecoveryInProgress = jest.fn();
jest.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ setRecoveryInProgress: mockSetRecoveryInProgress }),
}));

import { ForgotPasswordCard } from "@/components/auth/ForgotPasswordCard";
import { ThemeProvider } from "@/hooks/use-theme";
import {
  requestPasswordReset,
  setNewPassword,
  verifyRecoveryCode,
} from "@/lib/auth/recovery";

const mRequest = requestPasswordReset as jest.Mock;
const mVerify = verifyRecoveryCode as jest.Mock;
const mSetPassword = setNewPassword as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
  mRequest.mockResolvedValue(undefined);
  mVerify.mockResolvedValue({ error: null });
  mSetPassword.mockResolvedValue({ error: null });
});

function renderCard() {
  return render(
    <ThemeProvider>
      <ForgotPasswordCard onBackToSignIn={jest.fn()} />
    </ThemeProvider>,
  );
}

async function reachCodeStep(utils: ReturnType<typeof renderCard>) {
  fireEvent.changeText(utils.getByLabelText("Email"), "user@example.com");
  fireEvent.press(utils.getByLabelText("Send code"));
  await waitFor(() => utils.getByLabelText("Verification code"));
}

it("asks for an email first", () => {
  const { getByLabelText } = renderCard();
  expect(getByLabelText("Email")).toBeTruthy();
  expect(getByLabelText("Send code")).toBeTruthy();
});

it("advances to the code step even when the request fails", async () => {
  // Enumeration safety: a network error, a rate limit, and an unknown address
  // must all look identical to the user.
  mRequest.mockRejectedValue(new Error("boom"));
  const utils = renderCard();

  await reachCodeStep(utils);

  expect(utils.getByLabelText("Verification code")).toBeTruthy();
  expect(utils.queryByText(/boom/i)).toBeNull();
});

it("holds the redirect guard from the moment a code is requested", async () => {
  // Verifying the code signs the user in before the new password exists; without
  // this the root layout would bounce them into the tabs at step 2.
  const utils = renderCard();
  await reachCodeStep(utils);

  expect(mockSetRecoveryInProgress).toHaveBeenCalledWith(true);
});

it("keeps a wrong code on the code step and shows why", async () => {
  mVerify.mockResolvedValue({ error: "That code is invalid or has expired." });
  const utils = renderCard();
  await reachCodeStep(utils);

  fireEvent.changeText(utils.getByLabelText("Verification code"), "000000");
  fireEvent.press(utils.getByLabelText("Verify code"));

  await waitFor(() => utils.getByText("That code is invalid or has expired."));
  expect(utils.getByLabelText("Verification code")).toBeTruthy();
  expect(utils.queryByLabelText("New password")).toBeNull();
});

it("rejects a code shorter than the minimum without calling the server", async () => {
  const utils = renderCard();
  await reachCodeStep(utils);

  fireEvent.changeText(utils.getByLabelText("Verification code"), "123");
  fireEvent.press(utils.getByLabelText("Verify code"));

  await waitFor(() => utils.getByText("Enter the full code from your email."));
  expect(mVerify).not.toHaveBeenCalled();
});

it("accepts the 8-digit code this Supabase project actually issues", async () => {
  // Regression: the field used to be capped at 6 characters, which made the
  // whole flow impossible to complete — GoTrue's MAILER_OTP_LENGTH is a project
  // setting in the 6-10 range and this project issues 8.
  const utils = renderCard();
  await reachCodeStep(utils);

  const field = utils.getByLabelText("Verification code");
  fireEvent.changeText(field, "96105910");
  fireEvent.press(utils.getByLabelText("Verify code"));

  await waitFor(() => expect(mVerify).toHaveBeenCalledWith("user@example.com", "96105910"));
});

it("moves to the password step once the code verifies", async () => {
  const utils = renderCard();
  await reachCodeStep(utils);

  fireEvent.changeText(utils.getByLabelText("Verification code"), "48291374");
  fireEvent.press(utils.getByLabelText("Verify code"));

  await waitFor(() => utils.getByLabelText("New password"));
  expect(mVerify).toHaveBeenCalledWith("user@example.com", "48291374");
});

it("blocks a mismatched confirmation", async () => {
  const utils = renderCard();
  await reachCodeStep(utils);
  fireEvent.changeText(utils.getByLabelText("Verification code"), "48291374");
  fireEvent.press(utils.getByLabelText("Verify code"));
  await waitFor(() => utils.getByLabelText("New password"));

  fireEvent.changeText(utils.getByLabelText("New password"), "Str0ng!pass");
  fireEvent.changeText(utils.getByLabelText("Confirm new password"), "Different1!");
  fireEvent.press(utils.getByLabelText("Update password"));

  await waitFor(() => utils.getByText("Those passwords don't match."));
  expect(mSetPassword).not.toHaveBeenCalled();
});

it("releases the redirect guard only after the password is changed", async () => {
  const utils = renderCard();
  await reachCodeStep(utils);
  fireEvent.changeText(utils.getByLabelText("Verification code"), "48291374");
  fireEvent.press(utils.getByLabelText("Verify code"));
  await waitFor(() => utils.getByLabelText("New password"));

  expect(mockSetRecoveryInProgress).not.toHaveBeenCalledWith(false);

  fireEvent.changeText(utils.getByLabelText("New password"), "Str0ng!pass");
  fireEvent.changeText(utils.getByLabelText("Confirm new password"), "Str0ng!pass");
  fireEvent.press(utils.getByLabelText("Update password"));

  await waitFor(() => expect(mSetPassword).toHaveBeenCalledWith("Str0ng!pass"));
  expect(mockSetRecoveryInProgress).toHaveBeenCalledWith(false);
});
