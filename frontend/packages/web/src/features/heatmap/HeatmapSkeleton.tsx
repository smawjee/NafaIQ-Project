import { useLang } from "@/hooks/use-lang";

export function HeatmapSkeleton({ height = 560 }: { height?: number }) {
  const { t } = useLang();
  return (
    <div
      className="flex w-full items-center justify-center rounded-[8px] border border-border bg-surface-alt"
      style={{ height }}
    >
      <div className="text-text-muted text-sm">{t("Loading market heatmap…")}</div>
    </div>
  );
}
