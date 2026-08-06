import { useLang } from "@/hooks/use-lang";
import { TrendingUp, TrendingDown, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { logoUrlFor } from "@/lib/psx/stock-search";
import { formatCompact } from "@/lib/format";
import type { ApiTreemapStock } from "@/lib/psx/types";

export function StockTooltip({
  stock,
  x,
  y,
  visible,
}: {
  stock: ApiTreemapStock | null;
  x: number;
  y: number;
  visible: boolean;
}) {
  const { t } = useLang();
  if (!stock || !visible) return null;

  const isUp = stock.change_pct >= 0;
  const logoUrl = logoUrlFor(stock.logoid);
  const sign = isUp ? "+" : "";
  // The backend leaves market_cap null rather than inventing one when
  // listed_shares is unknown, and sizes the tile off a price*sqrt(volume)
  // proxy instead. Say so — an unlabelled "—" reads as missing data when the
  // real answer is "the tile is sized on something other than market cap".
  const isVolumeProxy = stock.sizing_basis === "volume_proxy";

  return (
    <div
      className="pointer-events-none fixed z-50 max-w-[260px] rounded-[8px] border border-border bg-surface-alt p-3 text-xs shadow-lg"
      style={{
        left: Math.min(x + 12, window.innerWidth - 280),
        top: Math.min(y + 12, window.innerHeight - 200),
      }}
    >
      <div className="mb-2 flex items-center gap-2">
        {logoUrl ? (
          <img src={logoUrl} alt={stock.symbol} className="h-6 w-6 rounded-full bg-surface" />
        ) : (
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-surface text-[10px] font-bold text-text-secondary">
            {stock.symbol[0]}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-text-primary">{stock.symbol}</div>
          <div className="truncate text-[10px] text-text-muted">{stock.name}</div>
        </div>
      </div>
      <div className="space-y-1">
        {stock.sector && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-text-muted">{t("Sector")}</span>
            <span className="truncate text-end text-text-secondary">{t(stock.sector)}</span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-text-muted">{t("Price")}</span>
          <span className="font-mono tabular-nums text-text-primary">
            PKR {stock.price.toFixed(2)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">{t("Change")}</span>
          <span
            className={cn(
              "inline-flex items-center gap-0.5 font-mono tabular-nums font-semibold",
              isUp ? "text-bull" : "text-bear",
            )}
          >
            {isUp ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {sign}
            {stock.change_pct.toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">{t("Volume")}</span>
          <span className="font-mono tabular-nums text-text-secondary">
            {stock.volume.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-text-muted">{isVolumeProxy ? t("Tile size") : t("Mkt Cap")}</span>
          {isVolumeProxy ? (
            <span className="text-end text-text-secondary">{t("Volume-based estimate")}</span>
          ) : (
            <span className="font-mono tabular-nums text-text-secondary">
              {stock.market_cap != null ? formatCompact(stock.market_cap) : "—"}
            </span>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-1 border-t border-border pt-2 text-[10px] text-text-muted">
        <BarChart3 className="h-3 w-3" />
        {t("Click to view details")}
      </div>
    </div>
  );
}
