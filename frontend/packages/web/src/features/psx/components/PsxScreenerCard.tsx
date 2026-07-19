import { Link } from "@tanstack/react-router";
import { Filter } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { SignalBadge } from "@/components/market/SignalBadge";
import { fmtNum, type Signal } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import type { PsxScreenRow } from "@/features/psx/psx.utils";

export function PsxScreenerCard({
  rows,
  screenedCount,
  screenerStart,
  screenerEnd,
  currentPage,
  pageCount,
  onPrev,
  onNext,
  searchFilter,
  onSearchChange,
  sectorFilter,
  onSectorChange,
  sectors,
  signalFilter,
  onSignalChange,
}: {
  rows: PsxScreenRow[];
  screenedCount: number;
  screenerStart: number;
  screenerEnd: number;
  currentPage: number;
  pageCount: number;
  onPrev: () => void;
  onNext: () => void;
  searchFilter: string;
  onSearchChange: (value: string) => void;
  sectorFilter: string;
  onSectorChange: (value: string) => void;
  sectors: string[];
  signalFilter: string;
  onSignalChange: (value: string) => void;
}) {
  const { t } = useLang();
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{t("Stock Screener")}</h3>
          <p className="text-[11px] text-text-muted">
            {screenedCount > 0
              ? `${t("Showing")} ${screenerStart}-${screenerEnd} ${t("of")} ${screenedCount}`
              : t("No stocks match the selected filters.")}
          </p>
        </div>
        <div className="flex items-center gap-1 text-xs text-text-secondary">
          <button
            type="button"
            disabled={currentPage <= 1}
            onClick={onPrev}
            className="rounded-[6px] border border-border px-2 py-1 hover:bg-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("Prev")}
          </button>
          <span className="min-w-12 text-center font-mono tabular-nums">
            {currentPage}/{pageCount}
          </span>
          <button
            type="button"
            disabled={currentPage >= pageCount}
            onClick={onNext}
            className="rounded-[6px] border border-border px-2 py-1 hover:bg-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            {t("Next")}
          </button>
        </div>
      </div>
      <div className="mb-3 flex items-center gap-2">
        <Filter className="h-4 w-4 text-text-secondary" />
        <input
          type="text"
          value={searchFilter}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={t("Search symbol or sector...")}
          className="min-w-0 flex-1 rounded-[6px] border border-border bg-elevated px-2.5 py-1 text-xs text-text-primary placeholder:text-text-muted"
        />
        <select
          value={sectorFilter}
          onChange={(e) => onSectorChange(e.target.value)}
          className="rounded-[6px] border border-border bg-elevated px-2 py-1 text-xs font-medium text-text-primary"
        >
          <option value="All">{t("All Sectors")}</option>
          {sectors.map((sec) => (
            <option key={sec} value={sec}>
              {t(sec)}
            </option>
          ))}
        </select>
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {(
          ["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"] as (string | Signal)[]
        ).map((f) => (
          <button
            key={f}
            onClick={() => onSignalChange(f)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium",
              signalFilter === f
                ? "bg-bull text-bull-foreground"
                : "border border-border text-text-secondary hover:bg-hover",
            )}
          >
            {t(f)}
          </button>
        ))}
      </div>
      <div className="scrollbar-none overflow-x-auto">
        <table className="w-full min-w-[640px] text-xs">
          <thead>
            <tr className="border-b border-border text-left text-text-muted">
              <th className="py-2">{t("Stock")}</th>
              <th>{t("Sector")}</th>
              <th className="text-right">{t("Price")}</th>
              <th className="text-right">{t("Change")}</th>
              <th className="text-center">{t("Signal")}</th>
              <th className="text-right">RSI</th>
              <th className="text-right">{t("Volume")}</th>
              <th className="pr-2 text-right">{t("Mkt Cap")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => (
              <tr
                key={s.ticker}
                className={cn("cursor-pointer hover:bg-hover", i % 2 ? "bg-surface-alt" : "")}
              >
                <td className="py-2">
                  <Link
                    to="/stock/$ticker"
                    params={{ ticker: s.ticker }}
                    className="font-semibold text-bull"
                  >
                    {s.ticker}
                  </Link>
                </td>
                <td className="text-text-secondary">{t(s.sector)}</td>
                <td className="text-right font-mono tabular-nums text-text-primary">
                  {fmtNum(s.price)}
                </td>
                <td className="text-right">
                  <Change pct={s.changePct} />
                </td>
                <td className="text-center">
                  {s.signal ? (
                    <SignalBadge signal={s.signal} />
                  ) : (
                    <span className="text-text-muted" title={t("Signal unavailable")}>
                      —
                    </span>
                  )}
                </td>
                <td className="text-right font-mono tabular-nums">
                  {s.rsi == null ? (
                    <span className="text-text-muted" title={t("Not enough history")}>
                      —
                    </span>
                  ) : (
                    <span
                      className={cn(
                        s.rsi > 70
                          ? "text-bear"
                          : s.rsi < 30
                            ? "text-bull"
                            : "text-text-secondary",
                      )}
                      title={
                        s.rsi > 70
                          ? t("Overbought")
                          : s.rsi < 30
                            ? t("Oversold")
                            : t("Neutral")
                      }
                    >
                      {s.rsi.toFixed(0)}
                      {s.rsi > 70 ? " OB" : s.rsi < 30 ? " OS" : ""}
                    </span>
                  )}
                </td>
                <td className="text-right font-mono tabular-nums text-text-secondary">
                  {s.volume}
                </td>
                <td className="pr-2 text-right font-mono tabular-nums text-text-secondary">
                  {s.marketCap}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
