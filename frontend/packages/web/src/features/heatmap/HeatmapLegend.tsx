import { useLang } from "@/hooks/use-lang";
import { useEffect, useState } from "react";

export function HeatmapLegend({ asOf }: { asOf: string }) {
  const { t } = useLang();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const asOfMs = new Date(asOf).getTime();
  const ageSec = Math.max(0, Math.floor((now - asOfMs) / 1000));
  const ageLabel =
    ageSec < 60
      ? `${ageSec}s ago`
      : ageSec < 3600
        ? `${Math.floor(ageSec / 60)}m ago`
        : `${Math.floor(ageSec / 3600)}h ago`;

  return (
    <div className="flex items-center justify-between text-[11px] text-text-muted">
      <div className="flex items-center gap-2">
        <span>{t("Loss")}</span>
        <div
          className="h-2 w-32 rounded"
          style={{
            background:
              "linear-gradient(to right, color-mix(in srgb, var(--color-bear) 90%, transparent), color-mix(in srgb, var(--color-bear) 30%, transparent), color-mix(in srgb, var(--color-bull) 30%, transparent), color-mix(in srgb, var(--color-bull) 90%, transparent))",
          }}
        />
        <span>{t("Gain")}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-bull animate-pulse" />
        <span>{t("Updated")} {ageLabel}</span>
      </div>
    </div>
  );
}
