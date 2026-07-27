import { type ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Format a timestamp in Asia/Karachi (PKT) — the platform's canonical zone.
 * Colocated with the shared admin UI it's always used alongside; the HMR
 * fast-refresh rule only cares about component-only files, which this isn't.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function formatPkt(value: string | null | undefined, withTime = true): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-GB", {
    timeZone: "Asia/Karachi",
    year: "numeric",
    month: "short",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function Panel({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-border bg-card/60 shadow-sm", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-text-primary">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-text-muted">{description}</p>}
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  available = true,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  available?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</div>
      {available ? (
        <div className="mt-1 text-2xl font-semibold text-text-primary">{value}</div>
      ) : (
        <div className="mt-1 text-sm text-text-muted">Not tracked yet</div>
      )}
      {hint && available && <div className="mt-1 text-xs text-text-muted">{hint}</div>}
    </div>
  );
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-bull/10 text-bull border-bull/30",
  success: "bg-bull/10 text-bull border-bull/30",
  promoted: "bg-bull/10 text-bull border-bull/30",
  suspended: "bg-bear/10 text-bear border-bear/30",
  failure: "bg-bear/10 text-bear border-bear/30",
  red: "bg-bear/10 text-bear border-bear/30",
  restricted: "bg-amber-500/10 text-amber-500 border-amber-500/30",
  shadow: "bg-amber-500/10 text-amber-500 border-amber-500/30",
};

export function StatusBadge({ status }: { status: string }) {
  const key = status?.toLowerCase?.() ?? "";
  const style = STATUS_STYLES[key] ?? "bg-muted text-text-secondary border-border";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        style,
      )}
    >
      {status || "—"}
    </span>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border bg-muted px-1.5 py-0.5 text-[11px] font-medium text-text-secondary">
      {children}
    </span>
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-text-muted">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <AlertTriangle className="h-6 w-6 text-bear" />
      <p className="max-w-sm text-sm text-text-secondary">
        {message ?? "This didn't load. Please try again."}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium text-text-primary hover:bg-hover"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyBlock({ label = "Nothing here yet." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-sm text-text-muted">
      <Inbox className="h-6 w-6" /> {label}
    </div>
  );
}

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between gap-2 pt-3 text-xs text-text-muted">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="rounded-md border border-border px-2 py-1 disabled:opacity-40 hover:bg-hover"
        >
          Prev
        </button>
        <span className="px-1">
          {page} / {pages}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          className="rounded-md border border-border px-2 py-1 disabled:opacity-40 hover:bg-hover"
        >
          Next
        </button>
      </div>
    </div>
  );
}

export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return (
    <th
      className={cn(
        "whitespace-nowrap px-3 py-2 text-start text-xs font-semibold uppercase tracking-wide text-text-muted",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, className }: { children?: ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2 text-sm text-text-primary", className)}>{children}</td>;
}
