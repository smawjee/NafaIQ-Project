import { useState } from "react";
import { Video } from "lucide-react";
import { useLang } from "@/hooks/use-lang";

export function VideoPlayer({
  url,
  mode = "embed",
  captionsUrl,
  posterUrl,
}: {
  url: string;
  mode?: "embed" | "file";
  captionsUrl?: string | null;
  posterUrl?: string | null;
}) {
  const [failed, setFailed] = useState(false);
  const { t } = useLang();
  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-card border border-border bg-elevated">
      {failed ? (
        <div className="flex h-full flex-col items-center justify-center gap-2 text-text-muted">
          <Video className="h-8 w-8" strokeWidth={1.5} />
          <div className="text-sm">{t("Video loading…")}</div>
        </div>
      ) : mode === "file" ? (
        <video
          src={url}
          poster={posterUrl ?? undefined}
          controls
          playsInline
          preload="metadata"
          className="h-full w-full bg-black object-contain"
          onError={() => setFailed(true)}
        >
          {captionsUrl && <track kind="captions" src={captionsUrl} srcLang="en" default />}
        </video>
      ) : (
        <iframe
          src={url}
          title={t("Lesson video")}
          className="h-full w-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}
