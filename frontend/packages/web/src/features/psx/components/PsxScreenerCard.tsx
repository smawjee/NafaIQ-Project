import { Link, useNavigate } from "@tanstack/react-router";
import { Filter, Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { SignalBadge } from "@/components/market/SignalBadge";
import { SignalConfidence } from "@/features/signals/SignalConfidence";
import { SignalReasonList } from "@/features/signals/SignalReasonList";
import { SignalRiskChips } from "@/features/signals/SignalRiskChips";
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
  const navigate = useNavigate();

  /** The row has always looked clickable (`cursor-pointer`) but only the
   *  ticker cell actually navigated. Clicking anywhere else now opens the
   *  stock — except on nested controls (the signal popover, links), which
   *  handle their own clicks. */
  const openStock = (ticker: string) => navigate({ to: "/stock/$ticker", params: { ticker } });

  const isInteractive = (target: EventTarget | null) =>
    target instanceof Element && target.closest("a,button,select,input,[role='button']") !== null;

  const renderSignal = (s: PsxScreenRow) => {
    if (!s.signal) {
      return (
        <span className="text-text-muted" title={t("Signal unavailable")}>
          —
        </span>
      );
    }
    return (
      <div className="inline-flex items-center gap-1">
        <SignalBadge signal={s.signal} />
        {s.signalDetails && (
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                aria-label={`${s.ticker} signal details`}
                className="rounded-full p-0.5 text-text-muted hover:bg-hover hover:text-text-primary"
              >
                <Info className="h-3.5 w-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="center" className="w-80">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-text-primary">
                      {s.ticker} {t("Signal")}
                    </div>
                    <div className="text-[11px] text-text-muted">
                      {s.signalDetails.horizon} · {s.signalDetails.engine_version}
                    </div>
                  </div>
                  <SignalBadge signal={s.signalDetails.signal} />
                </div>
                <SignalConfidence
                  confidence={s.signalDetails.confidence}
                  signal={s.signalDetails.signal}
                />
                <SignalRiskChips signal={s.signalDetails} />
                <SignalReasonList signal={s.signalDetails} compact />
              </div>
            </PopoverContent>
          </Popover>
        )}
      </div>
    );
  };
  return (
    <Card className="overflow-hidden">
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
      <div className="mb-3 grid gap-2 md:grid-cols-[auto_minmax(220px,1fr)_minmax(220px,0.9fr)] md:items-center">
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
          className="min-w-0 rounded-[6px] border border-border bg-elevated px-2 py-1 text-xs font-medium text-text-primary"
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
          ["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL", "NO SIGNAL"] as (
            string | Signal
          )[]
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
      <div className="overflow-x-auto">
        <table className="w-full min-w-[780px] text-xs">
          <thead>
            <tr className="border-b border-border text-start text-text-muted">
              <th className="py-2">{t("Stock")}</th>
              <th>{t("Sector")}</th>
              <th className="text-end">{t("Price")}</th>
              <th className="text-end">{t("Change")}</th>
              <th className="text-center">{t("Signal")}</th>
              <th className="text-end">{t("Strength")}</th>
              <th className="text-end">{t("RSI")}</th>
              <th className="text-end">{t("Volume")}</th>
              <th className="pe-2 text-end">{t("Mkt Cap")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => (
              <tr
                key={s.ticker}
                onClick={(e) => {
                  if (isInteractive(e.target)) return;
                  openStock(s.ticker);
                }}
                className={cn(
                  "cursor-pointer hover:bg-hover focus-within:bg-hover",
                  i % 2 ? "bg-surface-alt" : "",
                )}
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
                <td className="text-end font-mono tabular-nums text-text-primary">
                  {fmtNum(s.price)}
                </td>
                <td className="text-end">
                  <Change pct={s.changePct} />
                </td>
                <td className="text-center">
                  {renderSignal(s)}
                  {s.signal == null && s.signalDetails != null && (
                    <span className="text-text-muted" title={t("Signal unavailable")}>
                      —
                    </span>
                  )}
                </td>
                <td className="text-end font-mono tabular-nums text-text-secondary">
                  {s.signalDetails ? `${s.signalDetails.confidence.toFixed(0)}%` : "—"}
                </td>
                <td className="text-end font-mono tabular-nums">
                  {s.rsi == null ? (
                    <span className="text-text-muted" title={t("Not enough history")}>
                      —
                    </span>
                  ) : (
                    <span
                      className={cn(
                        s.rsi > 70 ? "text-bear" : s.rsi < 30 ? "text-bull" : "text-text-secondary",
                      )}
                      title={
                        s.rsi > 70 ? t("Overbought") : s.rsi < 30 ? t("Oversold") : t("Neutral")
                      }
                    >
                      {s.rsi.toFixed(0)}
                      {s.rsi > 70 ? " OB" : s.rsi < 30 ? " OS" : ""}
                    </span>
                  )}
                </td>
                <td className="text-end font-mono tabular-nums text-text-secondary">{s.volume}</td>
                <td className="pe-2 text-end font-mono tabular-nums text-text-secondary">
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
