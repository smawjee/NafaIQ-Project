import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { SignalBadge } from "@/components/market/SignalBadge";
import { fmtNum } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import type { PsxScreenRow } from "@/features/psx/psx.utils";

type MoverTab = "Gainers" | "Losers" | "Most Active";

export function PsxMoversCard({
  moverTab,
  onMoverTabChange,
  movers,
}: {
  moverTab: MoverTab;
  onMoverTabChange: (tab: MoverTab) => void;
  movers: PsxScreenRow[];
}) {
  const { t } = useLang();
  return (
    <Card className="h-fit overflow-hidden p-5">
      <div className="mb-3 flex flex-wrap gap-1">
        {(["Gainers", "Losers", "Most Active"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => onMoverTabChange(tab)}
            className={cn(
              "rounded-[6px] px-2.5 py-1 text-xs font-medium",
              moverTab === tab ? "bg-bull/15 text-bull" : "text-text-secondary hover:bg-hover",
            )}
          >
            {t(tab)}
          </button>
        ))}
      </div>
      <div className="space-y-1 text-xs">
        {movers.map((s, i) => (
          <div
            key={s.ticker}
            className={cn(
              "min-w-0 rounded-[8px] px-2 py-1.5",
              i % 2 ? "bg-surface-alt" : "bg-surface",
            )}
          >
            {/* Line 1: rank · ticker · price · change. Flex with a truncating
                ticker so the row can never overflow the (narrow) panel — the
                old fixed 6-column grid was wider than the panel and clipped the
                volume column. */}
            <div className="flex items-center gap-2">
              <span className="w-4 shrink-0 text-end tabular-nums text-text-muted">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate font-semibold text-text-primary">
                {s.ticker}
              </span>
              <span className="shrink-0 whitespace-nowrap font-mono tabular-nums text-text-primary">
                {fmtNum(s.price)}
              </span>
              <span className="shrink-0 whitespace-nowrap text-end">
                <Change pct={s.changePct} />
              </span>
            </div>
            {/* Line 2: signal on the left, volume on the right — the vertical
                expansion that lets the full "Strong Bullish/Bearish" label fit. */}
            <div className="mt-1 flex items-center justify-between gap-2 ps-6">
              {s.signal ? (
                <SignalBadge signal={s.signal} className="px-2 text-[9px] tracking-normal" />
              ) : (
                <span className="text-text-muted">—</span>
              )}
              <span className="shrink-0 whitespace-nowrap font-mono text-[11px] tabular-nums text-text-muted">
                {t("Vol")} {s.volume}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
