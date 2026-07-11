import { Link } from "@tanstack/react-router";
import { LayoutDashboard } from "lucide-react";
import { motion } from "@/components/shared/animations";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export function SidebarLink({
  to,
  label,
  icon: Icon,
  active,
}: {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  active: boolean;
}) {
  const { t } = useLang();
  return (
    <Link
      to={to}
      className={cn(
        "group relative flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13px] font-medium transition-colors duration-200",
        active ? "text-bull" : "text-text-secondary hover:bg-white/[0.04] hover:text-text-primary",
      )}
    >
      {/* shared sliding highlight */}
      {active && (
        <motion.span
          layoutId="sidebar-active-pill"
          className="absolute inset-0 rounded-[10px] bg-bull/[0.10]"
          transition={{ type: "spring", stiffness: 400, damping: 32 }}
        />
      )}
      {/* left-edge accent bar */}
      <span
        className={cn(
          "absolute start-0 top-1/2 z-[1] h-5 w-[3px] -translate-y-1/2 rounded-e-full bg-bull transition-opacity duration-200",
          active ? "opacity-100" : "opacity-0",
        )}
      />
      <Icon
        className={cn(
          "relative z-[1] h-5 w-5 shrink-0 transition-transform duration-200 group-hover:scale-110",
          active ? "text-bull" : "text-text-muted group-hover:text-text-primary",
        )}
        strokeWidth={1.75}
      />
      <span className="relative z-[1]">{t(label)}</span>
    </Link>
  );
}
