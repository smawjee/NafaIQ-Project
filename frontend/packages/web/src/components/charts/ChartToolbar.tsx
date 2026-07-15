import { CandlestickChart as CandleIcon, LineChart as LineIcon, ChevronDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export const TIMEFRAMES = ["1D", "1W", "1M", "3M", "6M", "1Y", "All"] as const;
export type Timeframe = (typeof TIMEFRAMES)[number];

export const INDICATORS = ["MA20", "MA50", "MA100", "MA200"] as const;
export type Indicator = (typeof INDICATORS)[number];

/** Human label per symbol for the dropdown trigger. The KSE-100 index is a
 * special case — every other value is a stock ticker shown alongside its name. */
export function symbolLabel(
  sym: string,
  t: (k: string) => string,
  nameFor?: (sym: string) => string,
) {
  if (sym === "KSE-100") return t("KSE-100 Index");
  return nameFor ? `${sym} · ${t(nameFor(sym))}` : sym;
}

export interface ChartToolbarProps {
  /** Currently-selected symbol. */
  sym: string;
  /** Resolves a ticker to a display name (for the trigger label). */
  nameFor: (sym: string) => string;
  /** Called when the user picks a different symbol from the dropdown. */
  onSymChange: (sym: string) => void;
  /** Timeframe + chart-type + MAs (lifted state). */
  tf: Timeframe;
  onTfChange: (tf: Timeframe) => void;
  type: "candle" | "line";
  onTypeChange: (t: "candle" | "line") => void;
  mas: Indicator[];
  onMasChange: (next: Indicator[]) => void;
  /** Hide the symbol picker (used in the per-stock detail page). */
  hideSymbolPicker?: boolean;
}

/**
 * Single source of truth for the chart toolbar (Phase 0 / B7). Lifts the
 * per-page time-frame / type / MAs / symbol state but leaves it to callers
 * so each page can wire its own persistence. PSX page wires `tfMap` in
 * localStorage; StockDetail page wires its own `tfMap`.
 */
export function ChartToolbar({
  sym,
  nameFor,
  onSymChange,
  tf,
  onTfChange,
  type,
  onTypeChange,
  mas,
  onMasChange,
  hideSymbolPicker = false,
}: ChartToolbarProps) {
  const { t } = useLang();

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      {!hideSymbolPicker && (
        <Popover>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="min-w-0 max-w-[260px] flex-1 truncate rounded-[6px] border border-border bg-elevated px-2.5 py-1.5 text-left text-sm font-medium text-text-primary sm:flex-none"
              aria-label={t("Select symbol")}
            >
              <span className="truncate">{symbolLabel(sym, t, nameFor)}</span>
              <ChevronDown className="ml-1 inline h-3.5 w-3.5 align-text-bottom text-text-secondary" />
            </button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className="w-[420px] p-2"
            onOpenAutoFocus={(e) => e.preventDefault()}
          >
            <StockSearchBox
              mode="navigate"
              autoFocus
              placeholder={t("Search symbol or company…")}
              onSelect={(r) => {
                onSymChange(r.symbol);
                document.body.click();
              }}
            />
          </PopoverContent>
        </Popover>
      )}

      <div className="flex flex-wrap gap-1">
        {TIMEFRAMES.map((label) => (
          <button
            key={label}
            type="button"
            onClick={() => onTfChange(label)}
            className={cn(
              "rounded-[6px] px-2 py-1 text-xs font-medium",
              tf === label
                ? "tf-active bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1 sm:ml-auto">
        <button
          type="button"
          onClick={() => onTypeChange("candle")}
          className={cn(
            "rounded-[6px] p-1.5",
            type === "candle" ? "bg-bull/15 text-bull" : "text-text-secondary hover:bg-hover",
          )}
          aria-label={t("Candlestick")}
        >
          <CandleIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onTypeChange("line")}
          className={cn(
            "rounded-[6px] p-1.5",
            type === "line" ? "bg-bull/15 text-bull" : "text-text-secondary hover:bg-hover",
          )}
          aria-label={t("Line")}
        >
          <LineIcon className="h-4 w-4" />
        </button>
        {INDICATORS.map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => onMasChange(mas.includes(m) ? mas.filter((x) => x !== m) : [...mas, m])}
            className={cn(
              "rounded-[6px] px-2 py-1 text-[10px] font-medium",
              mas.includes(m) ? "bg-info/20 text-info" : "text-text-muted hover:bg-hover",
            )}
          >
            {m}
          </button>
        ))}
      </div>
    </div>
  );
}
