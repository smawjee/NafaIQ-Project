import { Link, useRouterState } from "@tanstack/react-router";
import { motion } from "@/components/shared/animations";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { NAV } from "@/components/layout/layout.data";

export function BottomNav() {
  const { t: tr } = useLang();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const tabs = NAV.slice(0, 5);
  return (
    <nav className="glass-chrome safe-bottom fixed bottom-0 left-0 z-30 flex w-full items-stretch border-t border-white/5 lg:hidden">
      {tabs.map((t) => {
        const active = path === t.to || path.startsWith(t.to + "/");
        const label = "mobile" in t ? t.mobile : t.label;
        return (
          <Link
            key={t.to}
            to={t.to}
            className="flex min-h-[64px] flex-1 flex-col items-center justify-center gap-1 py-2"
          >
            <motion.span
              whileTap={{ scale: 0.9 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
              className="relative flex h-7 w-12 items-center justify-center rounded-full"
            >
              {active && (
                <motion.span
                  layoutId="bottomnav-active-pill"
                  className="absolute inset-0 rounded-full bg-gold/15"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <t.icon
                className={cn(
                  "relative z-[1] h-5 w-5 transition-colors",
                  active ? "text-gold" : "text-text-muted",
                )}
                strokeWidth={1.75}
              />
            </motion.span>
            <span
              className={cn(
                "text-[10px] font-medium transition-colors",
                active ? "text-gold" : "text-text-muted",
              )}
            >
              {tr(label)}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
