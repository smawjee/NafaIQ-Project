import { TICKER_ITEMS } from "@/lib/data";
import { cn } from "@/lib/utils";

/* ---------- seamless scrolling ticker ---------- */
export function TickerStrip() {
  // duplicate once so translateX(-50%) restarts at an invisible seam
  const items = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div className="relative z-10 overflow-hidden border-y border-border bg-surface py-3">
      {/* edge fade masks */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16 bg-gradient-to-r from-surface to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16 bg-gradient-to-l from-surface to-transparent" />
      <div className="flex w-max animate-[ticker_40s_linear_infinite] gap-8 whitespace-nowrap px-4 will-change-transform">
        {items.map((it, i) => (
          <span key={i} className="flex items-center gap-2 text-sm">
            <span className="font-medium text-text-secondary">{it.label}</span>
            <span className="font-mono tabular-nums text-text-primary">{it.value}</span>
            <span className={cn("font-mono tabular-nums", it.pct >= 0 ? "text-bull" : "text-bear")}>
              {it.pct >= 0 ? "▲+" : "▼"}
              {it.pct.toFixed(2)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
