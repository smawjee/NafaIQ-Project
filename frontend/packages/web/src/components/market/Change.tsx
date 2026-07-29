import { cn } from "@/lib/utils";
import { useLang, localizeDigits } from "@/hooks/use-lang";

export function Change({
  value,
  pct,
  className,
  pill,
}: {
  value?: number | string;
  pct: number;
  className?: string;
  pill?: boolean;
}) {
  useLang();
  const up = pct >= 0;
  const text = localizeDigits(`${up ? "▲" : "▼"}${up ? "+" : ""}${pct.toFixed(2)}%`);
  const displayValue =
    typeof value === "string" ? localizeDigits(value) : value;
  return (
    <span
      className={cn(
        "font-mono tabular-nums text-xs font-medium",
        up ? "text-bull" : "text-bear",
        pill && "rounded-[4px] px-1.5 py-0.5",
        pill && (up ? "bg-bull/15" : "bg-bear/15"),
        className,
      )}
    >
      {displayValue !== undefined && <span className="mr-1">{displayValue}</span>}
      {text}
    </span>
  );
}
