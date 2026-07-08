import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Menu } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CollapsibleColumnProps {
  side: "left" | "right";
  width: number;
  breakpoint: "lg" | "xl";
  collapsed: boolean;
  onToggle: (collapsed: boolean) => void;
  collapseButtonLabel: string;
  expandButtonLabel: string;
  persistKey?: string;
  hideOverflow?: boolean;
  children: ReactNode;
}

export function CollapsibleColumn({
  side,
  width,
  breakpoint,
  collapsed,
  onToggle,
  collapseButtonLabel,
  expandButtonLabel,
  persistKey,
  hideOverflow = true,
  children,
}: CollapsibleColumnProps) {
  const isLeft = side === "left";
  const hiddenClass = breakpoint === "lg" ? "lg:block" : "xl:block";
  const panelId = `col-${side}`;

  useEffect(() => {
    if (persistKey && typeof window !== "undefined") {
      window.localStorage.setItem(persistKey, collapsed ? "1" : "0");
    }
  }, [collapsed, persistKey]);

  const CollapseIcon = isLeft ? ChevronLeft : ChevronRight;

  return (
    <>
      {!collapsed && (
        <motion.aside
          id={panelId}
          animate={{ width }}
          initial={{ width }}
          transition={{ duration: 0.25, ease: "easeInOut" }}
          className={cn("hidden", hideOverflow && "overflow-hidden", hiddenClass)}
          aria-label={collapseButtonLabel}
        >
          <div className="shrink-0" style={{ width }}>
            {children}
          </div>
        </motion.aside>
      )}

      {collapsed && (
        <div className={cn("hidden w-0 shrink-0 overflow-visible", hiddenClass)}>
          <button
            onClick={() => onToggle(false)}
            className={cn(
              "relative top-[var(--sticky-rail)] flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface text-text-muted shadow-sm transition-all hover:border-bull hover:text-bull",
              isLeft ? "-ml-3" : "-mr-3",
            )}
            style={{ left: isLeft ? 0 : undefined, right: isLeft ? undefined : 0 }}
            aria-label={expandButtonLabel}
            title={expandButtonLabel}
            aria-expanded={false}
            aria-controls={panelId}
          >
            <Menu className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>
      )}
    </>
  );
}

export function CollapseHandle({
  side,
  onClick,
  ariaLabel,
}: {
  side: "left" | "right";
  onClick: () => void;
  ariaLabel: string;
}) {
  const Icon = side === "left" ? ChevronLeft : ChevronRight;
  return (
    <button
      onClick={onClick}
      aria-label={ariaLabel}
      aria-expanded
      aria-controls={`col-${side}`}
      className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface text-text-muted shadow-sm transition-all hover:border-bull hover:text-bull"
    >
      <Icon className="h-4 w-4" strokeWidth={1.5} />
    </button>
  );
}
