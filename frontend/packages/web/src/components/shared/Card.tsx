import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { motion, useReducedMotion, SPRING_UI } from "@/components/shared/animations";
import { InfoTip } from "@/components/shared/InfoTip";

export function Card({
  className,
  children,
  hover = true,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div
      className={cn("glass-card rounded-[14px] p-6", hover && "glass-card-hover", className)}
      {...props}
    >
      {children}
    </div>
  );
}

/**
 * Unified KPI/stat card: label (+ optional icon) on top, value anchored to
 * the bottom so a grid row of cards always lines up, trend-colored subtext.
 * `variant="hero"` renders the value larger for a primary metric.
 */
export function StatCard({
  label,
  value,
  sub,
  subColor,
  trend,
  icon: Icon,
  info,
  variant = "default",
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  /** Legacy escape hatch — prefer `trend`, which wins when both are set. */
  subColor?: string;
  trend?: "up" | "down" | "neutral";
  icon?: LucideIcon;
  /** Optional explanation shown via an "i" tooltip next to the label. */
  info?: string;
  variant?: "default" | "hero";
  className?: string;
}) {
  const { t } = useLang();
  const reduce = useReducedMotion();
  const subClass = trend
    ? trend === "up"
      ? "text-bull"
      : trend === "down"
        ? "text-bear"
        : "text-text-secondary"
    : (subColor ?? "text-text-secondary");
  const content = (
    <div className="flex h-full min-w-0 flex-col">
      <div className="flex items-start justify-between gap-2">
        <span className="flex items-center gap-1 text-xs font-medium leading-snug text-text-secondary">
          {t(label)}
          {info && <InfoTip label={info} />}
        </span>
        {Icon && (
          <Icon className="h-4 w-4 shrink-0 text-text-muted" strokeWidth={1.75} aria-hidden />
        )}
      </div>
      <div
        dir="ltr"
        className={cn(
          "mt-auto truncate pt-4 font-semibold tabular-nums tracking-tight text-text-primary",
          variant === "hero" ? "text-3xl" : "text-xl",
        )}
      >
        {value}
      </div>
      {sub && (
        <div dir="ltr" className={cn("mt-1 truncate text-xs font-medium tabular-nums", subClass)}>
          {sub}
        </div>
      )}
    </div>
  );
  if (reduce) {
    return <Card className={cn("p-5", className)}>{content}</Card>;
  }
  return (
    <motion.div
      className={cn("glass-card glass-card-hover rounded-[14px] p-5", className)}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.4 }}
      whileHover={{ y: -3 }}
      transition={SPRING_UI}
    >
      {content}
    </motion.div>
  );
}
