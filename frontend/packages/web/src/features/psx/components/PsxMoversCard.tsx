import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
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
    <Card>
      <div className="mb-2 flex gap-1">
        {(["Gainers", "Losers", "Most Active"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => onMoverTabChange(tab)}
            className={cn(
              "rounded-[6px] px-2.5 py-1 text-xs font-medium",
              moverTab === tab
                ? "bg-bull/15 text-bull"
                : "text-text-secondary hover:bg-hover",
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
              <td className="py-1.5 pl-2 text-text-muted">{i + 1}</td>
              <td className="font-semibold text-text-primary">{s.ticker}</td>
              <td className="text-right font-mono tabular-nums text-text-primary">
                {fmtNum(s.price)}
              </td>
              <td className="px-2 text-right">
                <Change pct={s.changePct} />
              </td>
              <td className="pr-2 text-right font-mono tabular-nums text-text-muted">
                {s.volume}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
