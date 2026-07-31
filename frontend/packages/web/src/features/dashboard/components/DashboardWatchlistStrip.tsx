import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { StockLogo } from "@/components/search/StockLogo";
import { logoUrlFor } from "@/lib/psx/stock-search";
import { STOCKS, fmtNum } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import type { EnrichedWatchlistItem } from "@/hooks/psx/use-watchlist";

export function DashboardWatchlistStrip({
  watchlistLoading,
  watchlist,
  useShowcaseDashboard,
  onRemove,
}: {
  watchlistLoading: boolean;
  watchlist: string[] | EnrichedWatchlistItem[];
  useShowcaseDashboard: boolean;
  onRemove: (symbol: string) => void;
}) {
  const { t } = useLang();
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Watchlist")}</h3>
      {watchlistLoading ? (
        <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-[120px] w-[160px] shrink-0 animate-pulse rounded-[8px] bg-surface-hover"
            />
          ))}
        </div>
      ) : watchlist.length === 0 ? (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("Your watchlist is empty. Add stocks from the PSX page to track them here.")}
        </Card>
      ) : useShowcaseDashboard ? (
        <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
          {(watchlist as string[]).map((tk) => {
            const s = STOCKS[tk];
            const price = s?.price ?? 0;
            const changePct = s?.changePct ?? 0;
            return (
              <div key={tk} className="group relative w-[160px] shrink-0">
                <Link
                  to="/psx"
                  className="block rounded-[8px] border border-border bg-surface p-3 transition hover:border-border-hover"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-text-primary">{tk}</span>
                    <Change pct={changePct} pill />
                  </div>
                  <div className="truncate text-[10px] text-text-muted">{t(s?.name ?? tk)}</div>
                  <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
                    {fmtNum(price)}
                  </div>
                  <div
                    className={cn(
                      "mt-1 text-[11px] font-mono tabular-nums",
                      changePct >= 0 ? "text-bull" : "text-bear",
                    )}
                  >
                    {changePct >= 0 ? "+" : ""}
                    {changePct.toFixed(2)}%
                  </div>
                </Link>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onRemove(tk);
                    toast(`${tk} ${t("removed from watchlist")}`);
                  }}
                  aria-label={`Remove ${tk} from watchlist`}
                  className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-text-muted opacity-0 transition hover:bg-surface-hover hover:text-text-primary group-hover:opacity-100"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
          {(watchlist as EnrichedWatchlistItem[]).map((item) => {
            const hasPrice = item.price != null && item.price > 0;
            const changePct = item.change_pct ?? 0;
            return (
              <div key={item.symbol} className="group relative w-[160px] shrink-0">
                <Link
                  to={"/stock/" + item.symbol}
                  className="block rounded-[8px] border border-border bg-surface p-3 transition hover:border-border-hover"
                >
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 font-semibold text-text-primary">
                      <StockLogo symbol={item.symbol} logoUrl={logoUrlFor(item.logoid)} size={18} />
                      {item.symbol}
                    </span>
                    {hasPrice && <Change pct={changePct} pill />}
                  </div>
                  <div className="truncate text-[10px] text-text-muted">{item.company_name}</div>
                  <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
                    {hasPrice ? fmtNum(item.price as number) : "—"}
                  </div>
                  {hasPrice ? (
                    <div
                      className={cn(
                        "mt-1 text-[11px] font-mono tabular-nums",
                        changePct >= 0 ? "text-bull" : "text-bear",
                      )}
                    >
                      {changePct >= 0 ? "+" : ""}
                      {changePct.toFixed(2)}%
                    </div>
                  ) : (
                    <div className="mt-1 text-[11px] text-text-muted">{t("Price unavailable")}</div>
                  )}
                </Link>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onRemove(item.symbol);
                    toast(`${item.symbol} ${t("removed from watchlist")}`);
                  }}
                  aria-label={`Remove ${item.symbol} from watchlist`}
                  className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-text-muted opacity-0 transition hover:bg-surface-hover hover:text-text-primary group-hover:opacity-100"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
