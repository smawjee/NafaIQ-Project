import { useEffect, useRef, useState } from "react";
import { Search, Plus, Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStockSearch } from "@/hooks/psx/use-stock-search";
import type { StockSearchResult } from "@/lib/psx/stock-search";
import { StockLogo } from "@/components/search/StockLogo";

export interface StockSearchBoxProps {
  /** "add" shows a plus / Added state; "navigate" is a suggestion list. */
  mode: "add" | "navigate";
  /** Called when a result is chosen (click / Enter). */
  onSelect: (result: StockSearchResult) => void;
  /** Upper-cased symbols already in the watchlist (for "add" mode). */
  addedSymbols?: string[];
  /** "inline" renders results in flow (popover); "floating" overlays a dropdown. */
  variant?: "inline" | "floating";
  placeholder?: string;
  autoFocus?: boolean;
  className?: string;
}

/**
 * Reusable stock search: debounced ticker + company-name search over the PSX
 * universe with live prices. Keyboard: up/down to move, Enter to select,
 * Escape to clear/close. Used by Watchlist add and the global search bar.
 */
export function StockSearchBox({
  mode,
  onSelect,
  addedSymbols = [],
  variant = "inline",
  placeholder,
  autoFocus,
  className,
}: StockSearchBoxProps) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(variant === "inline");
  const { results, loading, error, isEmpty, hasQuery } = useStockSearch(query);
  const added = new Set(addedSymbols.map((s) => s.toUpperCase()));
  const listRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => setActive(0), [query]);

  // keep the highlighted row in view
  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  // outside click closes the floating dropdown
  useEffect(() => {
    if (variant !== "floating") return;
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [variant]);

  function choose(r: StockSearchResult) {
    if (mode === "add" && added.has(r.symbol.toUpperCase())) return;
    onSelect(r);
    if (mode === "navigate") {
      setQuery("");
      setOpen(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const r = results[active];
      if (r) choose(r);
    } else if (e.key === "Escape") {
      if (query) setQuery("");
      else setOpen(false);
      e.currentTarget.blur();
    }
  }

  const showResults = open && (variant === "inline" || hasQuery || loading);

  const list = (
    <div ref={listRef} className="max-h-72 overflow-y-auto py-1">
      {loading ? (
        <div className="flex items-center justify-center gap-2 py-6 text-xs text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading stocks…
        </div>
      ) : error ? (
        <div className="py-6 text-center text-xs text-bear">
          Couldn't load stocks. Please try again.
        </div>
      ) : isEmpty ? (
        <div className="py-6 text-center text-xs text-text-muted">No stocks found</div>
      ) : (
        results.map((r, i) => {
          const isAdded = mode === "add" && added.has(r.symbol.toUpperCase());
          return (
            <button
              key={r.symbol}
              data-idx={i}
              type="button"
              disabled={isAdded}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(r)}
              className={cn(
                "flex w-full items-center gap-2 rounded-[6px] px-2 py-1.5 text-left transition-colors",
                i === active ? "bg-white/[0.06]" : "hover:bg-hover",
                isAdded && "opacity-50",
              )}
            >
              <StockLogo symbol={r.symbol} logoUrl={r.logoUrl} size={22} />
              <span className="shrink-0 text-sm font-semibold text-bull">{r.symbol}</span>
              <span className="flex-1 truncate text-[11px] text-text-muted">{r.name}</span>
              {r.price != null ? (
                <span className="shrink-0 text-right">
                  <span className="block font-mono text-[12px] tabular-nums text-text-primary">
                    {r.price.toFixed(2)}
                  </span>
                  {r.changePct != null ? (
                    <span
                      className={cn(
                        "block font-mono text-[10px] tabular-nums",
                        r.changePct >= 0 ? "text-bull" : "text-bear",
                      )}
                    >
                      {r.changePct >= 0 ? "+" : ""}
                      {r.changePct.toFixed(2)}%
                    </span>
                  ) : null}
                </span>
              ) : null}
              {mode === "add" ? (
                isAdded ? (
                  <span className="flex shrink-0 items-center gap-1 text-[10px] text-text-muted">
                    <Check className="h-3.5 w-3.5" />
                    Added
                  </span>
                ) : (
                  <Plus className="h-4 w-4 shrink-0 text-bull" />
                )
              ) : null}
            </button>
          );
        })
      )}
    </div>
  );

  return (
    <div ref={rootRef} className={cn("relative flex flex-col", className)}>
      <div className="relative">
        <Search className="pointer-events-none absolute start-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => setOpen(true)}
          autoFocus={autoFocus}
          aria-label="Search stocks"
          placeholder={placeholder ?? "Search stocks (e.g. HBL, Engro)…"}
          className="h-9 w-full rounded-[8px] border border-border bg-surface ps-8 pe-3 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-bull"
        />
      </div>

      {variant === "inline" ? (
        <div className="mt-1">{list}</div>
      ) : (
        showResults && (
          <div className="glass-chrome absolute top-11 z-50 w-full overflow-hidden rounded-[12px] border border-border px-1 shadow-2xl">
            {list}
          </div>
        )
      )}
    </div>
  );
}
