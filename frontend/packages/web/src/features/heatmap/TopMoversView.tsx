import { useLang } from "@/hooks/use-lang";
import { Link } from "@tanstack/react-router";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ApiTreemap } from "@/lib/psx/types";

export function TopMoversView({ data }: { data: ApiTreemap }) {
  const { t } = useLang();

  const allStocks = data.sectors.flatMap((s) =>
    s.stocks.map((st) => ({ ...st, sector: s.name }))
  );
  const top30 = [...allStocks]
    .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
    .slice(0, 30);

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
          {top30.map((s, i) => {
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
                  {s.market_cap >= 1e9
                    ? `${(s.market_cap / 1e9).toFixed(1)}B`
                    : s.market_cap >= 1e6
                      ? `${(s.market_cap / 1e6).toFixed(1)}M`
                      : s.market_cap.toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
