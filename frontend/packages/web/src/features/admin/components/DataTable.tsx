/**
 * The console's single table implementation.
 *
 * Deliberately generic over the row type so every list screen (users, audit,
 * admins, flags, monitoring blocks) gets identical sorting, selection, column
 * control, keyboard behaviour and empty/error handling for free. Pages supply
 * columns; they never hand-roll `<table>` markup.
 */
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown, Columns3, Download, X } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { Button, IconButton, SectionLabel } from "./primitives";
import { ErrorBlock, NoResultsBlock, TableSkeleton } from "./states";
import { downloadCsv } from "@/features/admin/lib/format";

export interface Column<T> {
  /** Stable key — used for sort state, column visibility and CSV headers. */
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Enables the header sort control. The parent owns the actual sorting. */
  sortable?: boolean;
  align?: "start" | "end";
  /** Tailwind width class, e.g. "w-40". */
  width?: string;
  /** Allow the admin to hide this column. Defaults to true. */
  hideable?: boolean;
  defaultHidden?: boolean;
  /** Plain value for CSV export; falls back to omitting the column. */
  exportValue?: (row: T) => unknown;
  /** Hide below the `lg` breakpoint to keep mobile tables readable. */
  secondary?: boolean;
}

export interface SortState {
  id: string;
  dir: "asc" | "desc";
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  /** Row-level caption for screen readers and the CSV filename. */
  label: string;

  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;

  sort?: SortState | null;
  onSortChange?: (sort: SortState | null) => void;

  /** Opt into bulk selection by passing both. */
  selectedIds?: Set<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  /** Rendered in the selection bar; receives the current selection. */
  bulkActions?: (ids: string[], clear: () => void) => ReactNode;

  onRowClick?: (row: T) => void;
  /** Marks the visually-primary row (e.g. the record open in a drawer). */
  activeRowId?: string | null;

  /** Filters are applied upstream; drives the "no results" copy + clear action. */
  hasFilters?: boolean;
  onClearFilters?: () => void;
  emptyState?: ReactNode;

  enableExport?: boolean;
  enableColumnControl?: boolean;
  toolbar?: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  label,
  isLoading,
  isError,
  onRetry,
  sort,
  onSortChange,
  selectedIds,
  onSelectionChange,
  bulkActions,
  onRowClick,
  activeRowId,
  hasFilters,
  onClearFilters,
  emptyState,
  enableExport = true,
  enableColumnControl = true,
  toolbar,
  footer,
  className,
}: DataTableProps<T>) {
  const captionId = useId();
  const { t } = useLang();
  const selectable = !!selectedIds && !!onSelectionChange;

  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(columns.filter((c) => c.defaultHidden).map((c) => c.id)),
  );
  const visible = useMemo(() => columns.filter((c) => !hidden.has(c.id)), [columns, hidden]);

  const pageIds = useMemo(() => rows.map(getRowId), [rows, getRowId]);
  const allSelected =
    selectable && pageIds.length > 0 && pageIds.every((id) => selectedIds!.has(id));
  const someSelected = selectable && pageIds.some((id) => selectedIds!.has(id)) && !allSelected;

  // The "select all" box is tri-state; `indeterminate` is DOM-only, so it has
  // to be assigned imperatively.
  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = !!someSelected;
  }, [someSelected]);

  function toggleAll() {
    if (!selectable) return;
    const next = new Set(selectedIds!);
    if (allSelected) pageIds.forEach((id) => next.delete(id));
    else pageIds.forEach((id) => next.add(id));
    onSelectionChange!(next);
  }

  function toggleRow(id: string) {
    if (!selectable) return;
    const next = new Set(selectedIds!);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectionChange!(next);
  }

  function cycleSort(col: Column<T>) {
    if (!col.sortable || !onSortChange) return;
    if (!sort || sort.id !== col.id) onSortChange({ id: col.id, dir: "asc" });
    else if (sort.dir === "asc") onSortChange({ id: col.id, dir: "desc" });
    else onSortChange(null);
  }

  function exportCsv() {
    const cols = visible.filter((c) => c.exportValue);
    if (cols.length === 0) return;
    downloadCsv(
      `nafaiq-${label.toLowerCase().replace(/\s+/g, "-")}-${new Date().toISOString().slice(0, 10)}.csv`,
      cols.map((c) => c.id),
      rows.map((r) => cols.map((c) => c.exportValue!(r))),
    );
  }

  const selectedCount = selectable ? pageIds.filter((id) => selectedIds!.has(id)).length : 0;
  // Rows selected on other pages. Bulk actions deliberately only act on the
  // current page (that is the set the admin can actually see), so any remainder
  // has to be surfaced rather than silently ignored.
  const offPageCount = selectable ? selectedIds!.size - selectedCount : 0;
  const showControls = enableColumnControl || enableExport || toolbar;

  return (
    <div className={cn("flex flex-col", className)}>
      {showControls && (
        <div className="flex min-h-11 flex-wrap items-center justify-between gap-2 px-4 py-2.5">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{toolbar}</div>
          <div className="flex shrink-0 items-center gap-1.5">
            {enableExport && (
              <Button
                size="sm"
                variant="outline"
                icon={<Download className="h-3.5 w-3.5" />}
                onClick={exportCsv}
                disabled={rows.length === 0}
                // Export covers the rows currently loaded, not the whole result
                // set. Saying so prevents a 25-row file being mistaken for a
                // full extract of a 5,000-row table.
                title={`Download the ${rows.length} row${rows.length === 1 ? "" : "s"} currently shown as CSV`}
              >
                <span className="hidden sm:inline">{t("Export")}</span>
              </Button>
            )}
            {enableColumnControl && (
              <ColumnMenu columns={columns} hidden={hidden} onChange={setHidden} />
            )}
          </div>
        </div>
      )}

      {/* Bulk-selection bar. Only mounts when something is selected so it never
          steals vertical space from the table at rest. */}
      {selectable && selectedCount > 0 && (
        <div className="flex flex-wrap items-center gap-3 border-y border-primary/25 bg-primary/8 px-4 py-2">
          <span className="tabular text-xs font-medium text-primary">{selectedCount} selected</span>
          <div className="flex flex-wrap items-center gap-1.5">
            {bulkActions?.(
              pageIds.filter((id) => selectedIds!.has(id)),
              () => onSelectionChange!(new Set()),
            )}
          </div>
          <IconButton
            label={t("Clear selection")}
            size="sm"
            className="ms-auto"
            onClick={() => onSelectionChange!(new Set())}
          >
            <X className="h-3.5 w-3.5" />
          </IconButton>
        </div>
      )}

      <div className="min-h-0 overflow-x-auto">
        {isLoading ? (
          <TableSkeleton cols={visible.length + (selectable ? 1 : 0)} />
        ) : isError ? (
          <ErrorBlock onRetry={onRetry} />
        ) : rows.length === 0 ? (
          hasFilters ? (
            <NoResultsBlock onClear={onClearFilters} />
          ) : (
            (emptyState ?? <NoResultsBlock />)
          )
        ) : (
          <table className="w-full border-collapse" aria-describedby={captionId}>
            <caption id={captionId} className="sr-only">
              {label}
            </caption>
            <thead>
              <tr className="border-b border-border">
                {selectable && (
                  <th scope="col" className="w-10 px-3 py-2.5">
                    <input
                      ref={selectAllRef}
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      aria-label={t("Select all rows on this page")}
                      className="h-3.5 w-3.5 cursor-pointer accent-[var(--color-primary)]"
                    />
                  </th>
                )}
                {visible.map((col) => {
                  const active = sort?.id === col.id;
                  return (
                    <th
                      key={col.id}
                      scope="col"
                      aria-sort={
                        active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"
                      }
                      className={cn(
                        "sticky top-0 z-10 whitespace-nowrap bg-card px-3 py-2.5",
                        "text-[11px] font-semibold uppercase tracking-wide text-text-muted",
                        col.align === "end" ? "text-end" : "text-start",
                        col.width,
                        col.secondary && "hidden lg:table-cell",
                      )}
                    >
                      {col.sortable && onSortChange ? (
                        <button
                          type="button"
                          onClick={() => cycleSort(col)}
                          className={cn(
                            "inline-flex cursor-pointer items-center gap-1 rounded transition-colors hover:text-text-primary",
                            active && "text-primary",
                          )}
                        >
                          {col.header}
                          {active ? (
                            sort!.dir === "asc" ? (
                              <ArrowUp className="h-3 w-3" aria-hidden />
                            ) : (
                              <ArrowDown className="h-3 w-3" aria-hidden />
                            )
                          ) : (
                            <ChevronsUpDown className="h-3 w-3 opacity-40" aria-hidden />
                          )}
                        </button>
                      ) : (
                        col.header
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const id = getRowId(row);
                const isSelected = selectable && selectedIds!.has(id);
                const isActive = activeRowId === id;
                return (
                  <tr
                    key={id}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    // Row click is a shortcut, never the only path — every row
                    // also contains a real focusable link or action button.
                    className={cn(
                      "border-b border-border/60 transition-colors duration-150",
                      onRowClick && "cursor-pointer",
                      isActive ? "bg-primary/8" : isSelected ? "bg-primary/5" : "hover:bg-hover",
                    )}
                  >
                    {selectable && (
                      <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRow(id)}
                          aria-label={`Select row ${id}`}
                          className="h-3.5 w-3.5 cursor-pointer accent-[var(--color-primary)]"
                        />
                      </td>
                    )}
                    {visible.map((col) => (
                      <td
                        key={col.id}
                        className={cn(
                          "px-3 py-2.5 text-sm text-text-primary",
                          col.align === "end" ? "text-end" : "text-start",
                          col.secondary && "hidden lg:table-cell",
                        )}
                      >
                        {col.cell(row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {footer && !isLoading && !isError && rows.length > 0 && (
        <div className="border-t border-border px-4 py-2.5">{footer}</div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function ColumnMenu<T>({
  columns,
  hidden,
  onChange,
}: {
  columns: Column<T>[];
  hidden: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  const { t, isUrdu } = useLang();
  const hideable = columns.filter((c) => c.hideable !== false);
  if (hideable.length === 0) return null;
  return (
    <DropdownMenu.Root dir={isUrdu ? "rtl" : "ltr"}>
      <DropdownMenu.Trigger asChild>
        <Button size="sm" variant="outline" icon={<Columns3 className="h-3.5 w-3.5" />}>
          <span className="hidden sm:inline">{t("Columns")}</span>
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-50 min-w-48 rounded-xl border border-border bg-popover p-1.5 shadow-[var(--admin-elev-3)]"
        >
          <SectionLabel className="px-2 py-1.5">{t("Visible columns")}</SectionLabel>
          {hideable.map((col) => (
            <DropdownMenu.CheckboxItem
              key={col.id}
              checked={!hidden.has(col.id)}
              onCheckedChange={(checked) => {
                const next = new Set(hidden);
                if (checked) next.delete(col.id);
                else next.add(col.id);
                onChange(next);
              }}
              onSelect={(e) => e.preventDefault()}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-text-secondary outline-none data-[highlighted]:bg-hover data-[highlighted]:text-text-primary"
            >
              <span
                className={cn(
                  "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border",
                  hidden.has(col.id) ? "border-border" : "border-primary bg-primary",
                )}
              >
                {!hidden.has(col.id) && (
                  <svg viewBox="0 0 10 10" className="h-2.5 w-2.5 text-primary-foreground">
                    <path
                      d="M1 5l2.5 2.5L9 2"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </span>
              <span className="truncate">{col.header}</span>
            </DropdownMenu.CheckboxItem>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/* -------------------------------------------------------------------------- */

/** Pagination with a page-size control. Designed to sit in a table footer. */
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
  pageSizeOptions = [25, 50, 100],
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
  onPageSize?: (n: number) => void;
  pageSizeOptions?: number[];
}) {
  const { t } = useLang();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-text-muted">
      <span className="tabular">
        <span className="font-medium text-text-secondary">
          {from}–{to}
        </span>{" "}
        {t("of")} <span className="font-medium text-text-secondary">{total.toLocaleString()}</span>
      </span>

      <div className="flex items-center gap-3">
        {onPageSize && (
          <label className="flex items-center gap-1.5">
            <span className="hidden sm:inline">{t("Rows")}</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              className="h-7 cursor-pointer rounded-md border border-border bg-surface-alt px-1.5 text-xs text-text-secondary hover:border-border-hover focus:border-primary focus:outline-none"
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="flex items-center gap-1">
          <Button size="sm" variant="outline" onClick={() => onPage(page - 1)} disabled={page <= 1}>
            {t("Prev")}
          </Button>
          <span className="tabular px-2">
            {page} / {pages}
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onPage(page + 1)}
            disabled={page >= pages}
          >
            {t("Next")}
          </Button>
        </div>
      </div>
    </div>
  );
}
