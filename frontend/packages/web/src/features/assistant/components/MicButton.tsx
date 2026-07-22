// Voice capture for the assistant composer.
//
// Records with MediaRecorder, posts the clip to /api/assistant/transcribe
// (Whisper on Groq), and hands the transcript back to the CALLER, which puts it
// in the text input rather than sending it. That choice is deliberate: the user
// sees what was heard and can fix it before anything happens, which is what
// makes a misheard amount a visible edit instead of a wrong ledger row.
//
// Tap to start, tap to stop. Hold-to-talk was not used: a spoken command runs
// 3-8 seconds, which is an awkward length to hold, and press-and-hold is
// unreliable when the pointer leaves the button.

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, Square } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { transcribeAudio } from "@/lib/assistant/client";

// Matches ai_stt_max_seconds on the backend. Stopping here rather than letting
// the backend reject the upload means the user never records into a void.
const MAX_SECONDS = 30;

type State = "idle" | "recording" | "transcribing";

interface Props {
  disabled?: boolean;
  onTranscript(text: string): void;
}

function pickMimeType(): string | undefined {
  // Safari has no webm/opus; letting MediaRecorder choose its own default is
  // better than forcing an unsupported type and throwing at construction.
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported?.(type));
}

export function MicButton({ disabled, onTranscript }: Props) {
  const { lang, t } = useLang();
  const [state, setState] = useState<State>("idle");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const stopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (stopTimerRef.current) clearTimeout(stopTimerRef.current);
    stopTimerRef.current = null;
    // Release the mic, or the browser keeps showing the recording indicator.
    recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    recorderRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      toast.error(t("Voice input isn't supported in this browser."));
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      // Denied, or no device. Both are the user's to resolve, not retryable.
      toast.error(t("Microphone access was blocked. Enable it in your browser settings."));
      return;
    }

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recorderRef.current = recorder;
    const chunks: BlobPart[] = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      cleanup();
      if (blob.size === 0) {
        setState("idle");
        return;
      }
      setState("transcribing");
      void transcribeAudio(blob, lang)
        .then((text) => {
          if (text.trim()) onTranscript(text.trim());
          else toast.error(t("I couldn't hear anything. Try again."));
        })
        .catch((e) => toast.error(e instanceof Error ? e.message : t("Transcription failed")))
        .finally(() => setState("idle"));
    };

    recorder.start();
    setState("recording");
    stopTimerRef.current = setTimeout(stop, MAX_SECONDS * 1000);
  }, [cleanup, lang, onTranscript, stop, t]);

  const busy = state === "transcribing";
  const recording = state === "recording";

  return (
    <button
      type="button"
      onClick={() => (recording ? stop() : void start())}
      disabled={disabled || busy}
      aria-label={recording ? t("Stop recording") : t("Speak your command")}
      aria-pressed={recording}
      title={recording ? t("Stop recording") : t("Speak your command")}
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] border transition-colors disabled:opacity-50",
        recording
          ? "border-bear bg-bear/15 text-bear"
          : "border-border text-text-secondary hover:border-bull hover:text-bull",
      )}
    >
      {busy ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : recording ? (
        <Square className="h-3.5 w-3.5 fill-current" />
      ) : (
        <Mic className="h-4 w-4" />
      )}
    </button>
  );
}
