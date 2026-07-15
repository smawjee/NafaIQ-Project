import { useLang } from "@/hooks/use-lang";
import { Link } from "@tanstack/react-router";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCompact } from "@/lib/format";

/** One row of the movers table. Presentational — the caller ranks and slices;
 * this view must not be fed the treemap payload, which the backend caps to the
 * 20 largest stocks per sector and so hides small-cap movers entirely. */
export type TopMover = {
  symbol: string;
  sector: string;
  price: number;
  change_pct: number;
  volume: number;
  market_cap: number | null;
};

export function TopMoversView({ movers }: { movers: TopMover[] }) {
  const { t } = useLang();

  return (
    <div className="overflow-x-auto rounded-[8px] border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border bg-surface-alt text-left text-text-muted">
            <th className="px-3 py-2 font-semibold">#</th>
            <th className="px-3 py-2 font-semibold">{t("Symbol")}</th>
            <th className="px-3 py-2 font-semibold">{t("Sector")}</th>
            <th className="px-3 py-2 text-right font-semibold">{t("Price")}</th>
            <th className="px-3 py-2 text-right font-semibold">{t("Change")}</th>
            <th className="px-3 py-2 text-right font-semibold">{t("Volume")}</th>
            <th className="px-3 py-2 text-right font-semibold">{t("Mkt Cap")}</th>
          </tr>
        </thead>
        <tbody>
          {movers.map((s, i) => {
            const isUp = s.change_pct >= 0;
            return (
              <tr
                key={s.symbol}
                className="border-b border-border/50 hover:bg-hover"
              >
                <td className="px-3 py-1.5 text-text-muted">{i + 1}</td>
                <td className="px-3 py-1.5 font-semibold">
                  <Link
                    to="/stock/$ticker"
                    params={{ ticker: s.symbol }}
                    className="text-bull hover:underline"
                  >
                    {s.symbol}
                  </Link>
                </td>
                <td className="px-3 py-1.5 text-text-secondary">{t(s.sector)}</td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-text-primary">
                  {s.price.toFixed(2)}
                </td>
                <td className="px-3 py-1.5 text-right">
                  <span
                    className={cn(
                      "inline-flex items-center gap-0.5 font-mono tabular-nums font-semibold",
                      isUp ? "text-bull" : "text-bear"
                    )}
                  >
                    {isUp ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                    {Math.abs(s.change_pct).toFixed(2)}%
                  </span>
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-text-secondary">
                  {s.volume.toLocaleString()}
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-text-secondary">
                  {s.market_cap != null ? formatCompact(s.market_cap) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
