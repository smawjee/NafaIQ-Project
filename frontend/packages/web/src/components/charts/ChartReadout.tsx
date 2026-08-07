import { formatCompact, formatNumber } from "@/lib/format";
import {
  type ChartScale,
  formatTooltipLabel,
  priceDecimals,
} from "@/components/charts/chart-format";
import { cn } from "@/lib/utils";
import type { Candle } from "@/lib/data";

/**
 * Fixed OHLC readout pinned to the top-left of the plot, TradingView-style.
 *
 * This replaces the floating tooltip box the charts used to show. A tooltip
 * that follows the cursor necessarily sits ON the candles it describes — in
 * the reported screenshot it covered the four most recent bars, i.e. exactly
 * the ones the reader had moved the mouse there to inspect. A fixed readout
 * never occludes the series, and it stays populated (showing the latest bar)
 * when the pointer is away, so the numbers are readable without hovering at all.
 */
export function ChartReadout({
  bar,
  scale,
  decimals,
  className,
}: {
  bar: Candle | null | undefined;
  scale: ChartScale;
  /** Price precision, derived from the visible range by the parent chart. */
  decimals?: number;
  className?: string;
}) {
  if (!bar) return null;
  const dp = decimals ?? priceDecimals(bar.high - bar.low);
  const up = bar.close >= bar.open;
  const change = bar.close - bar.open;
  const changePct = bar.open ? (change / bar.open) * 100 : 0;

  return (
    <div
      className={cn(
        "pointer-events-none absolute start-2 top-1 z-10 flex flex-wrap items-baseline gap-x-3 gap-y-0.5",
        "font-mono text-[11px] tabular-nums leading-tight",
        className,
      )}
    >
      <span className="text-text-secondary">{formatTooltipLabel(bar.t, scale)}</span>
      <Field label="O" value={formatNumber(bar.open, dp)} up={up} />
      <Field label="H" value={formatNumber(bar.high, dp)} up={up} />
      <Field label="L" value={formatNumber(bar.low, dp)} up={up} />
      <Field label="C" value={formatNumber(bar.close, dp)} up={up} />
      <Field label="V" value={formatCompact(bar.volume)} up={up} muted />
      <span className={up ? "text-bull" : "text-bear"}>
        {up ? "+" : ""}
        {formatNumber(change, dp)} ({changePct.toFixed(2)}%)
      </span>
    </div>
  );
}

function Field({
  label,
  value,
  up,
  muted = false,
}: {
  label: string;
  value: string;
  up: boolean;
  muted?: boolean;
}) {
  return (
    <span>
      <span className="text-text-muted">{label} </span>
      <span className={muted ? "text-text-secondary" : up ? "text-bull" : "text-bear"}>
        {value}
      </span>
    </span>
  );
}
