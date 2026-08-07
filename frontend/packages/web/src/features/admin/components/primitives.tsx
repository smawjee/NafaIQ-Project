/**
 * Admin visual primitives.
 *
 * Everything here is presentational and unopinionated about data. Pages compose
 * these rather than hand-rolling Tailwind, which is what keeps 11 admin screens
 * looking like one product. Colors come only from semantic tokens, which the
 * `.admin-root` layer in styles.css re-points for the console.
 */
import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { initials } from "@/features/admin/lib/format";

/* -------------------------------------------------------------------------- */
/* Surface                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * The base container. `Panel` is the only card shape in the console — one
 * radius, one border, one elevation — so nothing looks like a stray component.
 */
export function Panel({
  title,
  description,
  actions,
  footer,
  children,
  className,
  bodyClassName,
  flush = false,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Remove body padding — for tables that manage their own insets. */
  flush?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border bg-card shadow-[var(--admin-elev-1)]",
        "transition-colors duration-200 hover:border-border-hover",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="truncate text-sm font-semibold text-text-primary">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-text-muted">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn(!flush && "p-4", bodyClassName)}>{children}</div>
      {footer && <div className="border-t border-border px-4 py-2.5">{footer}</div>}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Buttons                                                                     */
/* -------------------------------------------------------------------------- */

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80 shadow-[var(--admin-elev-1)]",
  secondary:
    "bg-elevated text-text-primary border border-border hover:border-border-hover hover:bg-hover",
  outline:
    "border border-border text-text-secondary hover:text-text-primary hover:border-border-hover hover:bg-hover",
  ghost: "text-text-secondary hover:text-text-primary hover:bg-hover",
  danger: "border border-bear/40 bg-bear/10 text-bear hover:bg-bear/20 hover:border-bear/60",
};

const SIZES: Record<Size, string> = {
  // 32px tall: dense enough for toolbars, and the parent rows keep the 44px
  // touch target on mobile via the `min-h-11` on toolbar wrappers.
  sm: "h-8 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3 text-sm gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex cursor-pointer items-center justify-center rounded-lg font-medium",
        "transition-all duration-150 ease-out",
        "disabled:cursor-not-allowed disabled:opacity-45",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

/** Square icon-only button. `label` is required — it becomes the accessible name. */
export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string; variant?: Variant; size?: Size }
>(function IconButton(
  { label, variant = "ghost", size = "md", className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex cursor-pointer items-center justify-center rounded-lg",
        "transition-all duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-45",
        VARIANTS[variant],
        size === "sm" ? "h-8 w-8" : "h-9 w-9",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});

/* -------------------------------------------------------------------------- */
/* Form controls                                                               */
/* -------------------------------------------------------------------------- */

const FIELD =
  "w-full rounded-lg border border-border bg-surface-alt px-3 text-sm text-text-primary " +
  "placeholder:text-text-muted transition-colors duration-150 " +
  "hover:border-border-hover focus:border-primary focus:outline-none " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} className={cn(FIELD, "h-9", className)} {...rest} />;
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(FIELD, "py-2", className)} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, ...rest }, ref) {
    return (
      <select ref={ref} className={cn(FIELD, "h-9 cursor-pointer pe-8", className)} {...rest} />
    );
  },
);

/** Label + control + optional hint/error. Errors render next to the field. */
export function Field({
  label,
  hint,
  error,
  htmlFor,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-xs font-medium text-text-secondary">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-bear">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Badges                                                                      */
/* -------------------------------------------------------------------------- */

/**
 * Status colours. Semantics are conveyed by the label text as well as the hue,
 * so the badge never relies on colour alone (WCAG 1.4.1).
 */
const STATUS_STYLES: Record<string, string> = {
  active: "bg-bull/12 text-bull border-bull/30",
  success: "bg-bull/12 text-bull border-bull/30",
  healthy: "bg-bull/12 text-bull border-bull/30",
  enabled: "bg-bull/12 text-bull border-bull/30",
  promoted: "bg-bull/12 text-bull border-bull/30",
  suspended: "bg-bear/12 text-bear border-bear/30",
  failure: "bg-bear/12 text-bear border-bear/30",
  error: "bg-bear/12 text-bear border-bear/30",
  down: "bg-bear/12 text-bear border-bear/30",
  red: "bg-bear/12 text-bear border-bear/30",
  restricted: "bg-warning/12 text-warning border-warning/30",
  degraded: "bg-warning/12 text-warning border-warning/30",
  stale: "bg-warning/12 text-warning border-warning/30",
  shadow: "bg-warning/12 text-warning border-warning/30",
  pending: "bg-warning/12 text-warning border-warning/30",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const key = status?.toLowerCase?.() ?? "";
  const style = STATUS_STYLES[key] ?? "bg-muted text-text-secondary border-border";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        style,
        className,
      )}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" aria-hidden />
      {status || "—"}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "danger" | "warning";
  className?: string;
}) {
  const tones = {
    neutral: "border-border bg-muted text-text-secondary",
    accent: "border-primary/30 bg-primary/10 text-primary",
    danger: "border-bear/30 bg-bear/10 text-bear",
    warning: "border-warning/30 bg-warning/10 text-warning",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Role chips get a stable colour per role so admins learn them by sight. */
const ROLE_TONE: Record<string, "accent" | "danger" | "warning" | "neutral"> = {
  super_admin: "danger",
  support_admin: "accent",
  finance_admin: "warning",
  data_admin: "accent",
  ai_admin: "accent",
  content_admin: "neutral",
  analyst_readonly: "neutral",
};

export function RoleBadge({ role, className }: { role: string; className?: string }) {
  return (
    <Badge tone={ROLE_TONE[role] ?? "neutral"} className={className}>
      {role.replace(/_/g, " ")}
    </Badge>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-border bg-muted px-1.5 font-sans text-[10px] font-medium text-text-muted">
      {children}
    </kbd>
  );
}

/* -------------------------------------------------------------------------- */
/* Data display                                                                */
/* -------------------------------------------------------------------------- */

/** Circular initials chip. Decorative — the adjacent text carries the identity. */
export function Avatar({
  email,
  size = "md",
  className,
}: {
  email: string | null | undefined;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    sm: "h-6 w-6 text-[10px]",
    md: "h-8 w-8 text-xs",
    lg: "h-11 w-11 text-sm",
  } as const;
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full",
        "border border-primary/25 bg-primary/12 font-semibold text-primary",
        sizes[size],
        className,
      )}
    >
      {initials(email)}
    </span>
  );
}

/**
 * KPI tile. `available: false` renders an explicit "not tracked" state rather
 * than a zero — the console never implies a real measurement it doesn't have.
 */
export function KpiCard({
  label,
  value,
  hint,
  icon,
  delta,
  available = true,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  /** Signed period-over-period change; `null` hides the chip. */
  delta?: { value: number; label: string } | null;
  available?: boolean;
  className?: string;
}) {
  const { t } = useLang();
  const positive = delta ? delta.value >= 0 : false;
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl border border-border bg-card p-4",
        "shadow-[var(--admin-elev-1)] transition-all duration-200",
        "hover:border-border-hover hover:shadow-[var(--admin-elev-2)]",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</span>
        {icon && <span className="shrink-0 text-text-muted">{icon}</span>}
      </div>
      {available ? (
        <>
          <div className="tabular mt-2 text-2xl font-semibold leading-none text-text-primary">
            {value}
          </div>
          <div className="mt-2 flex items-center gap-2">
            {delta && (
              <span
                className={cn(
                  "tabular inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
                  positive ? "bg-bull/12 text-bull" : "bg-bear/12 text-bear",
                )}
              >
                {positive ? "+" : ""}
                {delta.value}
                <span className="font-normal opacity-80"> {delta.label}</span>
              </span>
            )}
            {hint && <span className="text-xs text-text-muted">{hint}</span>}
          </div>
        </>
      ) : (
        <div className="mt-2 text-sm text-text-muted">{t("Not tracked yet")}</div>
      )}
    </div>
  );
}

/** Definition-list row used in detail panels. */
export function DataRow({
  label,
  value,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-1.5", className)}>
      <dt className="shrink-0 text-xs text-text-muted">{label}</dt>
      <dd className="min-w-0 truncate text-end text-sm text-text-primary">{value}</dd>
    </div>
  );
}

/** Small uppercase group heading used inside panels and the sidebar. */
export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Horizontal proportion bar — used for tier/plan distribution. */
export function MeterBar({
  segments,
  className,
}: {
  segments: { label: string; value: number; className: string }[];
  className?: string;
}) {
  const { t } = useLang();
  const total = segments.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return null;
  return (
    <div
      className={cn("flex h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      role="img"
      aria-label={segments.map((s) => `${t(s.label)}: ${s.value}`).join(", ")}
    >
      {segments.map((s) => (
        <div
          key={s.label}
          className={cn("h-full transition-all duration-500 ease-out", s.className)}
          style={{ width: `${(s.value / total) * 100}%` }}
        />
      ))}
    </div>
  );
}

/** Monospace JSON block for audit before/after payloads. */
export function CodeBlock({ value, label }: { value: unknown; label?: string }) {
  const { t } = useLang();
  return (
    <div className="min-w-0">
      {label && <SectionLabel className="mb-1">{t(label)}</SectionLabel>}
      <pre className="max-h-64 overflow-auto rounded-lg border border-border bg-surface-alt p-2.5 text-[11px] leading-relaxed text-text-secondary">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
