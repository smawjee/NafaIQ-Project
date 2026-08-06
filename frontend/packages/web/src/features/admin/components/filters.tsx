/**
 * Filter controls for list screens.
 *
 * All of them are controlled — the page owns filter state and feeds it into its
 * query key, so a filter change is always reflected in the data (there are no
 * decorative filters in this console).
 */
import { useEffect, useState, type ReactNode } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button, Select } from "./primitives";
import { useLang } from "@/hooks/use-lang";

/**
 * Search box with an internal debounce.
 *
 * Keeps its own immediate value so typing stays responsive, and only pushes to
 * the parent (and therefore the query) after `delay` ms of quiet. Re-syncs when
 * the parent clears the value externally.
 */
export function SearchInput({
  value,
  onChange,
  placeholder = "Search…",
  delay = 300,
  className,
  autoFocus,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  delay?: number;
  className?: string;
  autoFocus?: boolean;
}) {
  const { t } = useLang();
  const [local, setLocal] = useState(value);

  useEffect(() => {
    setLocal(value);
  }, [value]);

  useEffect(() => {
    if (local === value) return;
    const t = window.setTimeout(() => onChange(local), delay);
    return () => window.clearTimeout(t);
    // `onChange`/`value` are intentionally excluded: including them would
    // restart the timer on every parent render and the debounce would never fire.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local, delay]);

  return (
    <div className={cn("relative min-w-[200px] flex-1", className)}>
      <Search
        className="pointer-events-none absolute start-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted"
        aria-hidden
      />
      <input
        type="search"
        value={local}
        autoFocus={autoFocus}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={t(placeholder)}
        aria-label={t(placeholder)}
        className={cn(
          "h-9 w-full rounded-lg border border-border bg-surface-alt ps-8 pe-8 text-sm",
          "text-text-primary placeholder:text-text-muted transition-colors duration-150",
          "hover:border-border-hover focus:border-primary focus:outline-none",
        )}
      />
      {local && (
        <button
          type="button"
          onClick={() => setLocal("")}
          aria-label={t("Clear search")}
          className="absolute end-2 top-1/2 -translate-y-1/2 cursor-pointer rounded text-text-muted transition-colors hover:text-text-primary"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

export interface FilterOption {
  value: string;
  label: string;
}

/** Labelled dropdown filter. An empty string is always the "all" option. */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel = "All",
  className,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: FilterOption[];
  allLabel?: string;
  className?: string;
}) {
  const { t } = useLang();
  return (
    <Select
      value={value}
      aria-label={t(label)}
      onChange={(e) => onChange(e.target.value)}
      className={cn("w-auto min-w-[9rem]", value && "border-primary/40 text-primary", className)}
    >
      <option value="">{t(allLabel)}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {t(o.label)}
        </option>
      ))}
    </Select>
  );
}

export type DateRangePreset = "" | "24h" | "7d" | "30d" | "90d";

export const DATE_PRESETS: { value: DateRangePreset; label: string }[] = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

/**
 * Resolve a preset to an ISO lower bound, or null for "all time".
 * Kept as a pure function so pages can pass the result straight into a query key.
 */
export function presetToSince(preset: DateRangePreset): string | null {
  if (!preset) return null;
  const hours = preset === "24h" ? 24 : preset === "7d" ? 168 : preset === "30d" ? 720 : 2160;
  return new Date(Date.now() - hours * 3600_000).toISOString();
}

export function DateRangeFilter({
  value,
  onChange,
  className,
}: {
  value: DateRangePreset;
  onChange: (v: DateRangePreset) => void;
  className?: string;
}) {
  return (
    <FilterSelect
      label="Date range"
      allLabel="All time"
      value={value}
      onChange={(v) => onChange(v as DateRangePreset)}
      options={DATE_PRESETS}
      className={className}
    />
  );
}

/**
 * Filter toolbar. Renders its children in a wrapping row and appends a
 * "Clear all" action whenever at least one filter is active.
 */
export function FilterBar({
  children,
  active,
  onClear,
  className,
}: {
  children: ReactNode;
  /** Number of currently-applied filters. */
  active?: number;
  onClear?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("flex min-h-11 flex-wrap items-center gap-2", className)}>
      {children}
      {!!active && onClear && (
        <Button size="sm" variant="ghost" icon={<X className="h-3.5 w-3.5" />} onClick={onClear}>
          Clear {active === 1 ? "filter" : `${active} filters`}
        </Button>
      )}
    </div>
  );
}
