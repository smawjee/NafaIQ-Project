import { cn } from "@/lib/utils";
import type { Signal } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";

const styles: Record<Signal, string> = {
  "STRONG BUY": "border border-bull/30 bg-bull/15 text-bull font-bold",
  BUY: "border border-bull/25 bg-bull/10 text-bull",
  HOLD: "signal-hold border border-text-secondary/25 bg-text-secondary/10 text-text-secondary",
  SELL: "border border-warning/30 bg-warning/10 text-warning",
  "STRONG SELL": "border border-bear/30 bg-bear/15 text-bear font-bold",
  "NO SIGNAL": "border border-text-secondary/25 bg-text-secondary/10 text-text-muted",
};

// Display the Signals-V4 rating wording (bullish/bearish) instead of the legacy
// buy/sell labels the adapter maps to internally. The colours above already
// match — bullish is bull-green, bearish is bear-red — so this is display-only.
const labels: Record<Signal, string> = {
  "STRONG BUY": "Strong Bullish",
  BUY: "Bullish",
  HOLD: "Neutral",
  SELL: "Bearish",
  "STRONG SELL": "Strong Bearish",
  "NO SIGNAL": "No Signal",
};

export function SignalBadge({ signal, className }: { signal: Signal; className?: string }) {
  const { t } = useLang();
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center justify-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold tracking-wide whitespace-nowrap uppercase",
        styles[signal],
        className,
      )}
    >
      {t(labels[signal])}
    </span>
  );
}
