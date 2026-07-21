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
              "grid min-w-0 grid-cols-[1.5rem_minmax(4rem,1fr)_4.5rem_5rem_5.25rem_4.25rem] items-center rounded-[8px] py-1.5",
              i % 2 ? "bg-surface-alt" : "bg-surface",
            )}
          >
            <span className="text-right tabular-nums text-text-muted">{i + 1}</span>
            <span className="min-w-0 truncate pl-2 pr-2 font-semibold text-text-primary">
              {s.ticker}
            </span>
            <span className="whitespace-nowrap text-right font-mono tabular-nums text-text-primary">
              {fmtNum(s.price)}
            </span>
            <span className="whitespace-nowrap text-right">
              <Change pct={s.changePct} />
            </span>
            <span className="min-w-0 justify-self-end overflow-hidden">
              {s.signal ? (
                <SignalBadge signal={s.signal} className="max-w-full px-2 text-[9px] tracking-normal" />
              ) : (
                <span className="text-text-muted">-</span>
              )}
            </span>
            <span className="whitespace-nowrap text-right font-mono text-[11px] tabular-nums text-text-muted">
              {s.volume}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
