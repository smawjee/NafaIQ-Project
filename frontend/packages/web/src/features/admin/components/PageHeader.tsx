/**
 * Contextual page header: breadcrumbs, title, supporting copy, actions.
 *
 * Every admin route renders exactly one of these, which is what gives the
 * console a predictable "where am I / what can I do here" band at the top of
 * every screen.
 */
import { type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export interface Crumb {
  label: string;
  to?: string;
  params?: Record<string, string>;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  const { t } = useLang();
  if (items.length === 0) return null;
  return (
    <nav aria-label={t("Breadcrumb")} className="min-w-0">
      <ol className="flex flex-wrap items-center gap-1 text-xs text-text-muted">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1">
              {c.to && !last ? (
                <Link
                  to={c.to}
                  params={c.params}
                  className="truncate rounded transition-colors hover:text-text-primary"
                >
                  {c.label}
                </Link>
              ) : (
                <span
                  className={cn("truncate", last && "font-medium text-text-secondary")}
                  aria-current={last ? "page" : undefined}
                >
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight className="h-3 w-3 shrink-0 opacity-50" aria-hidden />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  meta,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  breadcrumbs?: Crumb[];
  actions?: ReactNode;
  /** Badges/status chips rendered inline after the title. */
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("space-y-2", className)}>
      {breadcrumbs && breadcrumbs.length > 0 && <Breadcrumbs items={breadcrumbs} />}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">{title}</h1>
            {meta}
          </div>
          {description && (
            <p className="max-w-3xl text-sm leading-relaxed text-text-muted">{description}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
