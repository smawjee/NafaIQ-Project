import { Link } from "@tanstack/react-router";
import { Info, Plus, Star, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { SignalBadge } from "@/components/market/SignalBadge";
import { SignalConfidence } from "@/features/signals/SignalConfidence";
import { SignalReasonList } from "@/features/signals/SignalReasonList";
import { SignalRiskChips } from "@/features/signals/SignalRiskChips";
import { STOCKS, fmtNum, type Signal } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";
import type { ApiSignalBreakdown } from "@/lib/psx/types";

export function PsxWatchlistCard({
  symbols,
  onAdd,
  onRemove,
  addOpen,
  onAddOpenChange,
  snapshot,
  symbolsData,
  batchSignals,
}: {
  symbols: string[];
  // Async-aware: the watchlist hook rolls back and rethrows on server refusal,
  // so callers here must await before reporting the outcome.
  onAdd: (symbol: string) => void | Promise<void>;
  onRemove: (symbol: string) => void | Promise<void>;
  addOpen: boolean;
  onAddOpenChange: (open: boolean) => void;
  snapshot?: { symbol: string; price?: number | null; change_pct?: number | null }[];
  symbolsData?: { symbol: string; name?: string | null }[];
  batchSignals?: {
    signals?: { symbol: string; signal?: string | null; confidence?: number | null }[];
  };
}) {
  const { t } = useLang();
  return (
    <Card>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">{t("Watchlist")}</h3>
        <Popover open={addOpen} onOpenChange={onAddOpenChange}>
          <PopoverTrigger asChild>
            <button className="flex items-center gap-1 text-xs font-medium text-bull transition-colors hover:text-bull/80">
              <Plus className="h-3.5 w-3.5" />
              {t("Add Stock")}
            </button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 p-2">
            <StockSearchBox
              mode="add"
              autoFocus
              addedSymbols={symbols}
              placeholder={t("Search stocks to add…")}
              onSelect={async (r) => {
                if (symbols.includes(r.symbol)) {
                  toast(`${r.symbol} ${t("is already in your watchlist")}`);
                  return;
                }
                // The server enforces the max_watchlist quota and rejects
                // unknown symbols — don't claim success before it answers.
                try {
                  await onAdd(r.symbol);
                  toast.success(`${r.symbol} ${t("added to watchlist")}`);
                } catch {
                  toast.error(`${t("Could not add")} ${r.symbol}. ${t("Please try again.")}`);
                }
              }}
            />
          </PopoverContent>
        </Popover>
      </div>
      <div className="space-y-1">
        {symbols.map((tk) => {
          const fallback = STOCKS[tk];
          const live = snapshot?.find((row) => row.symbol === tk);
          const rawPrice = live?.price ?? fallback?.price ?? null;
          const hasPrice = rawPrice != null && rawPrice > 0;
          const livePrice = rawPrice ?? 0;
          const liveChangePct = live?.change_pct ?? fallback?.changePct ?? 0;
          const liveName = symbolsData?.find((s) => s.symbol === tk)?.name ?? fallback?.name ?? tk;
          const signalForSymbol =
            batchSignals?.signals?.find((s: { symbol: string }) => s.symbol === tk)?.signal ??
            fallback?.signal ??
            null;
          const signalDetails = batchSignals?.signals?.find(
            (s: { symbol: string }) => s.symbol === tk,
          ) as ApiSignalBreakdown | undefined;
          return (
            <div
              key={tk}
              className="group flex items-center gap-2 rounded-[6px] px-2 py-1.5 hover:bg-hover"
            >
              {/* State indicator only. Removal is the explicit trash button at
                  the end of the row — two controls that both remove (and both
                  named "Remove HBL") made the star a hidden, guessable action. */}
              <Star
                aria-hidden="true"
                className="wl-star h-3.5 w-3.5 shrink-0 text-bull"
                fill="#00d4aa"
              />
              <Link
                to="/stock/$ticker"
                params={{ ticker: tk }}
                className="flex flex-1 items-center gap-2"
              >
                <div className="flex-1">
                  <div className="wl-symbol text-sm font-semibold text-bull">{tk}</div>
                  <div className="text-[10px] text-text-muted">{t(liveName)}</div>
                </div>
                <div className="text-right">
                  {hasPrice ? (
                    <>
                      <div className="font-mono text-sm tabular-nums text-text-primary">
                        {fmtNum(livePrice)}
                      </div>
                      <Change pct={liveChangePct} />
                    </>
                  ) : (
                    <div
                      className="font-mono text-sm tabular-nums text-text-muted"
                      title={t("Live price unavailable")}
                    >
                      —
                    </div>
                  )}
                </div>
                {signalForSymbol ? (
                  <div className="flex items-center gap-1">
                    <SignalBadge signal={signalForSymbol as Signal} />
                    {signalDetails?.reasons && (
                      <Popover>
                        <PopoverTrigger asChild>
                          <span
                            role="button"
                            tabIndex={0}
                            aria-label={`${tk} signal details`}
                            className="rounded-full p-0.5 text-text-muted hover:bg-hover hover:text-text-primary"
                          >
                            <Info className="h-3.5 w-3.5" />
                          </span>
                        </PopoverTrigger>
                        <PopoverContent align="end" className="w-80">
                          <div className="space-y-3">
                            <SignalConfidence
                              confidence={signalDetails.confidence}
                              signal={signalDetails.signal}
                            />
                            <SignalRiskChips signal={signalDetails} />
                            <SignalReasonList signal={signalDetails} compact />
                          </div>
                        </PopoverContent>
                      </Popover>
                    )}
                  </div>
                ) : (
                  <span className="text-[10px] font-semibold uppercase text-text-muted">
                    {t("No signal")}
                  </span>
                )}
              </Link>
              {/* Sibling of the Link, never nested inside it — a button inside
                  an anchor is invalid and swallows the click on some browsers.
                  Always rendered rather than hover-only: hover does not exist
                  on touch, which is where this shortcut matters most. */}
              <button
                type="button"
                onClick={async () => {
                  // Await it: onRemove rolls back and rethrows if the server
                  // rejects, so confirming before it settles would claim a
                  // removal that did not happen.
                  try {
                    await onRemove(tk);
                    toast(`${tk} ${t("removed from watchlist")}`);
                  } catch {
                    toast.error(`${t("Could not remove")} ${tk}. ${t("Please try again.")}`);
                  }
                }}
                aria-label={`${t("Remove")} ${tk} ${t("from watchlist")}`}
                title={`${t("Remove")} ${tk} ${t("from watchlist")}`}
                className="shrink-0 rounded-[6px] p-1 text-text-muted transition-colors hover:bg-bear/10 hover:text-bear focus-visible:ring-2 focus-visible:ring-bear/40 focus-visible:outline-none"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
