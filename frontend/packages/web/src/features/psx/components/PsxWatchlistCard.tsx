import { Link } from "@tanstack/react-router";
import { Info, Plus, Star } from "lucide-react";
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
import type { ApiSignalV2 } from "@/lib/psx/types";

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
  onAdd: (symbol: string) => void;
  onRemove: (symbol: string) => void;
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
              onSelect={(r) => {
                if (symbols.includes(r.symbol)) {
                  toast(`${r.symbol} ${t("is already in your watchlist")}`);
                  return;
                }
                onAdd(r.symbol);
                toast.success(`${r.symbol} ${t("added to watchlist")}`);
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
          ) as ApiSignalV2 | undefined;
          return (
            <div
              key={tk}
              className="group flex items-center gap-2 rounded-[6px] px-2 py-1.5 hover:bg-hover"
            >
              <button
                onClick={() => {
                  onRemove(tk);
                  toast(`${tk} ${t("removed from watchlist")}`);
                }}
                aria-label={`Remove ${tk}`}
                className="shrink-0"
              >
                <Star className="wl-star h-3.5 w-3.5 text-bull" fill="#00d4aa" />
              </button>
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
            </div>
          );
        })}
      </div>
    </Card>
  );
}
