import { cn } from "@/lib/utils";
import { signalTone } from "@/features/signals/signal.utils";
import { useLang } from "@/hooks/use-lang";

export function SignalConfidence({
  confidence,
  signal,
  className,
}: {
  confidence: number;
  signal?: string | null;
  className?: string;
}) {
  const { t } = useLang();
  const pct = Math.max(0, Math.min(100, confidence || 0));
  return (
    <div className={cn("min-w-[88px]", className)}>
      <div className="mb-1 flex items-center justify-between gap-2 text-[10px] text-text-muted">
        <span>{t("Setup strength")}</span>
        <span className={cn("font-mono font-semibold tabular-nums", signalTone(signal))}>
          {pct.toFixed(0)}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-border">
        <div
          className={cn(
            "h-full rounded-full",
            signal === "SELL" || signal === "STRONG SELL" ? "bg-bear" : "bg-bull",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
