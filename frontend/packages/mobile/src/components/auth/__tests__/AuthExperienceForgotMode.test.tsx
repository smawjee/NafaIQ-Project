// AuthExperience -> ForgotPasswordCard wiring.
//
// ForgotPassword.test.tsx renders the card directly, which proves the card but
// not that anything can REACH it. This covers the seam: the "Forgot password?"
// control only exists in sign-in mode, tapping it swaps the card in, and "Back
// to sign in" swaps it back out.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { fireEvent, waitFor } from "@testing-library/react-native";
import React from "react";

jest.mock("@/lib/auth/recovery", () => ({
  requestPasswordReset: jest.fn().mockResolvedValue(undefined),
  verifyRecoveryCode: jest.fn().mockResolvedValue({ error: null }),
  setNewPassword: jest.fn().mockResolvedValue({ error: null }),
}));

jest.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    signInWithPassword: jest.fn().mockResolvedValue({ error: null }),
    signUpWithPassword: jest.fn().mockResolvedValue({ error: null }),
    signInWithGoogle: jest.fn().mockResolvedValue({ error: null }),
    setRecoveryInProgress: jest.fn(),
  }),
}));

import { AuthExperience } from "@/components/auth/AuthExperience";
import { renderWithProviders } from "@/test-utils";

function renderAuth() {
  // intro=false skips the 2.8s hero animation and renders the form immediately.
  return renderWithProviders(<AuthExperience />);
}

it("offers the forgot-password link in sign-in mode", async () => {
  const { getByLabelText } = renderAuth();
  await waitFor(() => getByLabelText("Forgot password"));
  expect(getByLabelText("Forgot password")).toBeTruthy();
});

it("hides the forgot-password link in sign-up mode", async () => {
  // There is no password to recover for an account that does not exist yet.
  const { getByText, queryByLabelText, getByLabelText } = renderAuth();
  await waitFor(() => getByLabelText("Forgot password"));

  fireEvent.press(getByText("Sign up"));

  await waitFor(() => expect(queryByLabelText("Forgot password")).toBeNull());
});

it("swaps in the recovery card when the link is tapped", async () => {
  const { getByLabelText, queryByLabelText } = renderAuth();
  await waitFor(() => getByLabelText("Forgot password"));

  fireEvent.press(getByLabelText("Forgot password"));

  await waitFor(() => getByLabelText("Send code"));
  // The sign-in form is gone, so there is no way to submit stale credentials.
  expect(queryByLabelText("Sign in")).toBeNull();
  expect(queryByLabelText("Continue with Google")).toBeNull();
});

it("returns to the sign-in form from the recovery card", async () => {
  const { getByLabelText } = renderAuth();
  await waitFor(() => getByLabelText("Forgot password"));

  fireEvent.press(getByLabelText("Forgot password"));
  await waitFor(() => getByLabelText("Back to sign in"));

  fireEvent.press(getByLabelText("Back to sign in"));

  await waitFor(() => getByLabelText("Sign in"));
  expect(getByLabelText("Forgot password")).toBeTruthy();
});
