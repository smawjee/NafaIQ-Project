import { useLang } from "@/hooks/use-lang";
import { MapPin } from "lucide-react";

export function HeatmapEmptyState({ height = 560 }: { height?: number }) {
  const { t } = useLang();
  return (
    <div
      className="flex w-full flex-col items-center justify-center gap-2 rounded-[8px] border border-border bg-surface-alt p-6 text-center"
      style={{ height }}
    >
      <MapPin className="h-8 w-8 text-text-muted" />
      <p className="text-sm font-semibold text-text-primary">
        {t("Heatmap data unavailable")}
      </p>
      <p className="max-w-md text-xs text-text-muted">
        {t(
          "Market snapshot updates every 5 seconds. If the market is closed, prices reflect the last close. Heatmap will repopulate when live data resumes."
        )}
      </p>
    </div>
  );
}
