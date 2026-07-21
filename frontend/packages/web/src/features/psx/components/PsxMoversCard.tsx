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
      <div className="mb-3 flex gap-1">
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
      <table className="w-full text-xs">
        <tbody>
          {movers.map((s, i) => (
            <tr key={s.ticker} className={cn(i % 2 ? "bg-surface-alt" : "bg-surface")}>
              <td className="w-7 py-1.5 pl-1 pr-2 text-right tabular-nums text-text-muted">
                {i + 1}
              </td>
              <td className="whitespace-nowrap pr-3 font-semibold text-text-primary">
                {s.ticker}
              </td>
              <td className="whitespace-nowrap pl-2 text-right font-mono tabular-nums text-text-primary">
                {fmtNum(s.price)}
              </td>
              <td className="whitespace-nowrap px-1.5 text-right">
                <Change pct={s.changePct} />
              </td>
              <td className="whitespace-nowrap px-1.5 text-right">
                {s.signal ? (
                  <SignalBadge signal={s.signal} className="px-2 text-[9px] tracking-normal" />
                ) : (
                  <span className="text-text-muted">-</span>
                )}
              </td>
              <td className="whitespace-nowrap pr-1 text-right font-mono text-[11px] tabular-nums text-text-muted">
                {s.volume}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
