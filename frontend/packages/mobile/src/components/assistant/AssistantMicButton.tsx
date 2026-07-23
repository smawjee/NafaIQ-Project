// Voice capture for the assistant composer. Port of web MicButton.tsx onto
// expo-audio: records an m4a/AAC clip (HIGH_QUALITY preset — .m4a on both
// platforms, accepted by the backend's Whisper route), posts it to
// /api/assistant/transcribe, and hands the transcript back to the CALLER,
// which puts it in the text input rather than sending it. The user sees what
// was heard and can fix it before anything happens.
//
// Tap to start, tap to stop (30s auto-stop, matching backend
// ai_stt_max_seconds). Hold-to-talk was deliberately not used, same as web.

import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet } from "react-native";

import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { Mic, Square } from "@/lib/icons";
import { transcribeAudio } from "@/lib/assistant/client";

const MAX_SECONDS = 30;

type State = "idle" | "recording" | "transcribing";

interface Props {
  disabled?: boolean;
  onTranscript(text: string): void;
  /** Recording/transcription problems surface here; the screen toasts them. */
  onError(message: string): void;
}

export function AssistantMicButton({ disabled, onTranscript, onError }: Props) {
  const { lang, t } = useLang();
  const { colors } = useTheme();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [state, setState] = useState<State>("idle");
  const stopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
    stopTimerRef.current = null;
  }, []);

  const stop = useCallback(async () => {
    clearTimer();
    try {
      await recorder.stop();
    } catch {
      setState("idle");
      return;
    }
    // Recording keeps other audio ducked until the mode is reverted.
    void setAudioModeAsync({ allowsRecording: false });
    const uri = recorder.uri;
    if (!uri) {
      setState("idle");
      return;
    }
    setState("transcribing");
    try {
      const text = (await transcribeAudio(uri, lang)).trim();
      if (text) onTranscript(text);
      else onError(t("I couldn't hear anything. Try again."));
    } catch (e) {
      onError(e instanceof Error ? e.message : t("Transcription failed"));
    } finally {
      setState("idle");
    }
  }, [clearTimer, lang, onError, onTranscript, recorder, t]);

  const start = useCallback(async () => {
    const permission = await requestRecordingPermissionsAsync();
    if (!permission.granted) {
      // Denied, or no device. Both are the user's to resolve, not retryable.
      onError(t("Microphone access was blocked. Enable it in your device settings."));
      return;
    }
    try {
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch (e) {
      onError(e instanceof Error ? e.message : t("Could not start recording"));
      return;
    }
    setState("recording");
    stopTimerRef.current = setTimeout(() => void stop(), MAX_SECONDS * 1000);
  }, [onError, recorder, stop, t]);

  // Unmounting mid-recording must release the mic and the audio mode.
  useEffect(
    () => () => {
      clearTimer();
      void setAudioModeAsync({ allowsRecording: false });
    },
    [clearTimer],
  );

  const busy = state === "transcribing";
  const recording = state === "recording";

  return (
    <Pressable
      onPress={() => (recording ? void stop() : void start())}
      disabled={disabled || busy}
      accessibilityRole="button"
      accessibilityLabel={recording ? t("Stop recording") : t("Speak your command")}
      accessibilityState={{ selected: recording, disabled: disabled || busy }}
      style={[
        styles.btn,
        {
          borderColor: recording ? colors.bear : colors.border,
          backgroundColor: recording ? colors.bear + "26" : colors.glassFill,
        },
        (disabled || busy) && { opacity: 0.5 },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={colors.textSecondary} size="small" />
      ) : recording ? (
        <Square color={colors.bear} size={14} fill={colors.bear} />
      ) : (
        <Mic color={colors.textSecondary} size={17} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 44,
    height: 44,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});
