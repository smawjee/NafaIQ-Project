import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { usePsxSymbols } from "@/hooks/psx/use-psx";
import { useLang } from "@/hooks/use-lang";
import { cn } from "@/lib/utils";

/** How many matches to render. The full list is ~1,077 symbols; painting all of
 *  them on every keystroke is wasted work when nobody scrolls past the first
 *  screenful. Ranking (below) is what makes a short list sufficient. */
const MAX_RESULTS = 50;

/**
 * Searchable picker over every PSX symbol.
 *
 * Replaces the hardcoded `STOCKS = ["HBL","ENGRO","LUCK","OGDC"]` that made 1,073
 * of the exchange's symbols unreachable from the alerts screen. Reads the live
 * list via `usePsxSymbols()` (GET /api/symbols), so it stays correct as PSX
 * lists and delists.
 *
 * Deliberately not a `<select>`: a thousand-option native select is unusable on
 * mobile and unsearchable on desktop. Deliberately not shadcn `command` either
 * — that needs `cmdk`, which is not a dependency of this app, and this is one
 * input plus a filtered list.
 */
export function SymbolPicker({
  value,
  onChange,
  disabled,
  id,
  className,
}: {
  value: string;
  onChange: (symbol: string) => void;
  disabled?: boolean;
  id?: string;
  className?: string;
}) {
  const { t } = useLang();
  const { data: symbols, isLoading, isError } = usePsxSymbols();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const matches = useMemo(() => {
    const all = symbols ?? [];
    const term = query.trim().toUpperCase();
    if (!term) return all.slice(0, MAX_RESULTS);
    // Rank: exact ticker, then ticker prefix, then ticker contains, then name.
    // Without ranking, typing "HBL" buries Habib Bank under every company whose
    // NAME happens to contain those letters.
    const exact: typeof all = [];
    const prefix: typeof all = [];
    const contains: typeof all = [];
    const byName: typeof all = [];
    for (const s of all) {
      const ticker = s.symbol.toUpperCase();
      if (ticker === term) exact.push(s);
      else if (ticker.startsWith(term)) prefix.push(s);
      else if (ticker.includes(term)) contains.push(s);
      else if ((s.name ?? "").toUpperCase().includes(term)) byName.push(s);
    }
    return [...exact, ...prefix, ...contains, ...byName].slice(0, MAX_RESULTS);
  }, [symbols, query]);

  useEffect(() => setHighlighted(0), [query]);

  // Keep the highlighted row in view during keyboard navigation.
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.children[highlighted] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [highlighted, open]);

  function choose(symbol: string) {
    onChange(symbol);
    setQuery("");
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const pick = matches[highlighted];
      if (pick) choose(pick.symbol);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const listboxId = id ? `${id}-listbox` : "symbol-picker-listbox";

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <div className="relative">
        {/* ps-/pe- (logical) not pl-/pr-: this screen renders RTL in Urdu. */}
        <Search
          className="pointer-events-none absolute start-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
          strokeWidth={1.75}
          aria-hidden
        />
        <input
          id={id}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-label={t("Search stock symbol")}
          autoComplete="off"
          disabled={disabled || isLoading}
          value={open ? query : value}
          placeholder={isLoading ? t("Loading symbols…") : t("Search symbol or company")}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          className="w-full rounded-[6px] border border-border bg-elevated px-3 py-2 ps-8 text-sm text-text-primary outline-none placeholder:text-text-muted disabled:opacity-60"
        />
        {value && !open && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label={t("Clear symbol")}
            className="absolute end-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {isError && (
        <p className="mt-1 text-xs text-bear">
          {t("Could not load symbols. Check your connection and try again.")}
        </p>
      )}

      {open && (
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-[8px] border border-border bg-surface shadow-lg"
        >
          {matches.length === 0 ? (
            <li className="px-3 py-2 text-sm text-text-muted">{t("No matching symbol")}</li>
          ) : (
            matches.map((s, i) => (
              <li
                key={s.symbol}
                role="option"
                aria-selected={i === highlighted}
                onMouseEnter={() => setHighlighted(i)}
                onMouseDown={(e) => {
                  // mousedown, not click: the input's blur would close the list
                  // before a click ever landed.
                  e.preventDefault();
                  choose(s.symbol);
                }}
                className={cn(
                  "flex cursor-pointer items-baseline gap-2 px-3 py-2 text-sm",
                  i === highlighted ? "bg-hover" : "",
                )}
              >
                <span className="font-semibold text-text-primary">{s.symbol}</span>
                <span className="truncate text-xs text-text-secondary">{s.name}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
