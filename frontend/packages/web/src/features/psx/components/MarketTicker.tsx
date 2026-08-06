import { STOCK_LIST, fmtNum } from "@/lib/data";
import { useMarketTickers } from "@/hooks/psx/use-psx";
import { useDemo } from "@/hooks/use-demo";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

export function MarketTicker() {
  const { t } = useLang();
  const { isDemo } = useDemo();
  const tickers = useMarketTickers(20);
  // Real users never see fabricated tickers: fall back to the static list only
  // in demo mode, otherwise render nothing until live data arrives.
  const rows = tickers.length
    ? tickers
    : isDemo
      ? STOCK_LIST.map((s) => ({
          symbol: s.ticker,
          name: s.name,
          sector: s.sector,
          price: s.price,
          change: 0,
          changePct: s.changePct,
          volume: 0,
        }))
      : [];
  const row = [...rows, ...rows];
  return (
    <div className="market-strip overflow-hidden rounded-[10px]">
      <div className="flex items-stretch">
        <div className="market-strip-live flex shrink-0 items-center gap-1.5 px-3 text-[11px] font-semibold uppercase tracking-wide">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-bull" />
          <span className="text-bull">{t("Live")}</span>
        </div>
        <div className="market-strip-tape flex-1 overflow-hidden py-2">
          <div className="flex w-max animate-ticker gap-6 ps-6">
            {row.map((s, i) => (
              <span key={i} className="flex items-center gap-2 whitespace-nowrap text-[12px]">
                <span className="market-strip-symbol font-semibold">{s.symbol}</span>
                <span className="market-strip-muted font-mono tabular-nums">{fmtNum(s.price)}</span>
                <span
                  className={cn(
                    "font-mono tabular-nums",
                    s.changePct >= 0 ? "text-bull" : "text-bear",
                  )}
                >
                  {s.changePct >= 0 ? "+" : ""}
                  {s.changePct.toFixed(2)}%
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
