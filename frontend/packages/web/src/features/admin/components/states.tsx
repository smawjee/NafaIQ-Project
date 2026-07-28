/**
 * Every non-happy path the console can land in, as one consistent set.
 *
 * Each state answers three questions: what happened, why it matters, and what
 * the admin can do next. A bare spinner or an unexplained blank panel is a bug,
 * not a state.
 */
import { type CSSProperties, type ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, Lock, RefreshCw, SearchX, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { Button } from "./primitives";

/* -------------------------------------------------------------------------- */
/* Skeletons                                                                   */
/* -------------------------------------------------------------------------- */

export function Shimmer({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} style={style} />;
}

/** Table placeholder that reserves the real row height, so there's no CLS. */
export function TableSkeleton({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-px" aria-hidden>
      <div className="flex gap-3 border-b border-border px-3 py-2.5">
        {Array.from({ length: cols }).map((_, i) => (
          <Shimmer key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-3 border-b border-border/50 px-3 py-3">
          {Array.from({ length: cols }).map((_, c) => (
            <Shimmer
              key={c}
              className="h-3.5 flex-1"
              // Fade successive rows so the placeholder reads as a list
              // receding into the fold rather than a flat grid.
              style={{ opacity: 1 - r * 0.06 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function KpiSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-hidden>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-4">
          <Shimmer className="h-3 w-20" />
          <Shimmer className="mt-3 h-7 w-16" />
          <Shimmer className="mt-2 h-3 w-24" />
        </div>
      ))}
    </div>
  );
}

export function PanelSkeleton({ lines = 4 }: { lines?: number }) {
  return (
    <div className="space-y-2.5" aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="flex items-center justify-between gap-4">
          <Shimmer className="h-3.5 w-1/3" />
          <Shimmer className="h-3.5 w-16" />
        </div>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Status blocks                                                               */
/* -------------------------------------------------------------------------- */

function StateShell({
  icon,
  title,
  body,
  action,
  tone = "muted",
}: {
  icon: ReactNode;
  title: string;
  body?: ReactNode;
  action?: ReactNode;
  tone?: "muted" | "danger" | "warning";
}) {
  const tones = {
    muted: "text-text-muted",
    danger: "text-bear",
    warning: "text-warning",
  } as const;
  return (
    <div
      role="status"
      className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center"
    >
      <div
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface-alt",
          tones[tone],
        )}
      >
        {icon}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-text-primary">{title}</p>
        {body && <p className="mx-auto max-w-sm text-xs text-text-muted">{body}</p>}
      </div>
      {action}
    </div>
  );
}

export function LoadingBlock({ label }: { label?: string }) {
  const { t } = useLang();
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 py-12 text-sm text-text-muted"
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label ?? t("Loading…")}
    </div>
  );
}

export function EmptyBlock({
  label,
  hint,
  action,
}: {
  label?: string;
  hint?: string;
  action?: ReactNode;
}) {
  const { t } = useLang();
  return (
    <StateShell
      icon={<Inbox className="h-5 w-5" />}
      title={label ?? t("Nothing here yet.")}
      body={hint}
      action={action}
    />
  );
}

/** No rows matched the *current filters* — distinct from "no data exists". */
export function NoResultsBlock({ onClear }: { onClear?: () => void }) {
  const { t } = useLang();
  return (
    <StateShell
      icon={<SearchX className="h-5 w-5" />}
      title={t("No results")}
      body={t("No records match the filters you've applied. Try widening or clearing them.")}
      action={
        onClear && (
          <Button size="sm" variant="outline" onClick={onClear}>
            {t("Clear filters")}
          </Button>
        )
      }
    />
  );
}

export function ErrorBlock({
  message,
  onRetry,
  detail,
}: {
  message?: string;
  onRetry?: () => void;
  detail?: string;
}) {
  const { t } = useLang();
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;
  if (offline) return <OfflineBlock onRetry={onRetry} />;
  return (
    <StateShell
      tone="danger"
      icon={<AlertTriangle className="h-5 w-5" />}
      title={message ?? t("This didn't load")}
      body={
        detail ??
        t("The request failed. This is usually transient — retry, or check System Health.")
      }
      action={
        onRetry && (
          <Button
            size="sm"
            variant="outline"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={onRetry}
          >
            {t("Retry")}
          </Button>
        )
      }
    />
  );
}

export function OfflineBlock({ onRetry }: { onRetry?: () => void }) {
  const { t } = useLang();
  return (
    <StateShell
      tone="warning"
      icon={<WifiOff className="h-5 w-5" />}
      title={t("You're offline")}
      body={t("The console can't reach the network. Data shown may be stale.")}
      action={
        onRetry && (
          <Button
            size="sm"
            variant="outline"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={onRetry}
          >
            {t("Retry")}
          </Button>
        )
      }
    />
  );
}

/**
 * Shown when the signed-in admin lacks the permission a surface requires.
 * Names the missing permission so they know exactly what to request — the
 * server enforces this independently; this is the explanatory UI.
 */
export function PermissionDenied({ permission }: { permission?: string }) {
  const { t } = useLang();
  return (
    <StateShell
      tone="warning"
      icon={<Lock className="h-5 w-5" />}
      title={t("You don't have access to this")}
      body={
        <>
          This area requires{" "}
          {permission ? (
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-text-secondary">
              {permission}
            </code>
          ) : (
            "an additional permission"
          )}
          . Ask a super administrator to grant it from your user profile.
        </>
      }
    />
  );
}

/**
 * Wraps a query's three states so pages don't repeat the ternary ladder.
 * Renders children only once data is present and non-empty.
 */
export function QueryState<T>({
  isLoading,
  isError,
  data,
  onRetry,
  skeleton,
  isEmpty,
  empty,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  data: T | undefined;
  onRetry?: () => void;
  skeleton?: ReactNode;
  isEmpty?: (d: T) => boolean;
  empty?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (isLoading) return <>{skeleton ?? <LoadingBlock />}</>;
  if (isError || data === undefined) return <ErrorBlock onRetry={onRetry} />;
  if (isEmpty?.(data)) return <>{empty ?? <EmptyBlock />}</>;
  return <>{children(data)}</>;
}
