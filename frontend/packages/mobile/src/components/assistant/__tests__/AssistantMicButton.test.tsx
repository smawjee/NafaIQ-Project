/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import React from "react";

const mockRecorder = {
  uri: "file:///rec.m4a",
  prepareToRecordAsync: jest.fn().mockResolvedValue(undefined),
  record: jest.fn(),
  stop: jest.fn().mockResolvedValue(undefined),
};
jest.mock("expo-audio", () => ({
  RecordingPresets: { HIGH_QUALITY: {} },
  useAudioRecorder: () => mockRecorder,
  requestRecordingPermissionsAsync: jest.fn(),
  setAudioModeAsync: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("@/lib/assistant/client", () => ({ transcribeAudio: jest.fn() }));

import { requestRecordingPermissionsAsync } from "expo-audio";

import { AssistantMicButton } from "@/components/assistant/AssistantMicButton";
import { ThemeProvider } from "@/hooks/use-theme";
import { transcribeAudio } from "@/lib/assistant/client";

const mPermission = requestRecordingPermissionsAsync as jest.Mock;
const mTranscribe = transcribeAudio as jest.Mock;

function renderMic() {
  const onTranscript = jest.fn();
  const onError = jest.fn();
  const utils = render(
    <ThemeProvider>
      <AssistantMicButton onTranscript={onTranscript} onError={onError} />
    </ThemeProvider>,
  );
  return { ...utils, onTranscript, onError };
}

beforeEach(() => jest.clearAllMocks());

describe("AssistantMicButton", () => {
  it("surfaces a friendly message when the mic permission is denied", async () => {
    mPermission.mockResolvedValue({ granted: false });
    const { getByLabelText, onError } = renderMic();

    fireEvent.press(getByLabelText("Speak your command"));

    await waitFor(() => expect(onError).toHaveBeenCalledWith(expect.stringContaining("Microphone")));
    expect(mockRecorder.record).not.toHaveBeenCalled();
  });

  it("records, stops, transcribes, and hands back the trimmed transcript", async () => {
    mPermission.mockResolvedValue({ granted: true });
    mTranscribe.mockResolvedValue("  add 500 for fuel  ");
    const { getByLabelText, onTranscript, onError } = renderMic();

    fireEvent.press(getByLabelText("Speak your command"));
    await waitFor(() => expect(mockRecorder.record).toHaveBeenCalled());

    // While recording the same button becomes the stop control.
    fireEvent.press(getByLabelText("Stop recording"));
    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("add 500 for fuel"));
    expect(mTranscribe).toHaveBeenCalledWith("file:///rec.m4a", "en");
    expect(onError).not.toHaveBeenCalled();

    // Back to idle: the mic label returns.
    await waitFor(() => expect(getByLabelText("Speak your command")).toBeTruthy());
  });

  it("reports transcription failures through onError, never a crash", async () => {
    mPermission.mockResolvedValue({ granted: true });
    mTranscribe.mockRejectedValue(new Error("Speech recognition unavailable"));
    const { getByLabelText, onTranscript, onError } = renderMic();

    fireEvent.press(getByLabelText("Speak your command"));
    await waitFor(() => expect(mockRecorder.record).toHaveBeenCalled());
    fireEvent.press(getByLabelText("Stop recording"));

    await waitFor(() => expect(onError).toHaveBeenCalledWith("Speech recognition unavailable"));
    expect(onTranscript).not.toHaveBeenCalled();
  });
});
