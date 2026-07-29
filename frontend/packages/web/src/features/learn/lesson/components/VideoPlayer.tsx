import { useState } from "react";
import { Video } from "lucide-react";
import { useLang } from "@/hooks/use-lang";

export function VideoPlayer({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);
  const { t } = useLang();
  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-card border border-border bg-elevated">
      {failed ? (
        <div className="flex h-full flex-col items-center justify-center gap-2 text-text-muted">
          <Video className="h-8 w-8" strokeWidth={1.5} />
          <div className="text-sm">{t("Video loading…")}</div>
        </div>
      ) : (
        <iframe
          src={url}
          title="Lesson video"
          className="h-full w-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}
