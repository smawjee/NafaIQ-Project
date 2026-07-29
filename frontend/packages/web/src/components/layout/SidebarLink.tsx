import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import { motion } from "@/components/shared/animations";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export function SidebarLink({
  to,
  label,
  icon: Icon,
  active,
  compact = false,
}: {
  to: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  compact?: boolean;
}) {
  const { t } = useLang();
  return (
    <Link
      to={to}
      className={cn(
        "premium-sidebar-link group relative flex h-10 items-center gap-2.5 rounded-[12px] px-3 text-sm font-medium transition-all duration-200",
        compact && "h-9 gap-2 rounded-[10px] px-2.5 text-[13px]",
        active && "is-active",
      )}
    >
      {active && (
        <motion.span
          layoutId="sidebar-active-pill"
          className={cn(
            "premium-sidebar-link-pill absolute inset-0 rounded-[12px]",
            compact && "rounded-[10px]",
          )}
          transition={{ type: "spring", stiffness: 420, damping: 34 }}
        />
      )}
      <span
        className={cn(
          "premium-sidebar-link-indicator absolute start-0 top-1/2 z-[1] h-5 w-[3px] -translate-y-1/2 rounded-e-full transition-opacity duration-200",
          active ? "opacity-100" : "opacity-0",
        )}
      />
      <Icon
        className={cn(
          "premium-sidebar-link-icon relative z-[1] h-5 w-5 shrink-0 transition-colors duration-200",
          compact && "h-[18px] w-[18px]",
        )}
        strokeWidth={1.9}
      />
      <span className="relative z-[1] truncate">{t(label)}</span>
    </Link>
  );
}
