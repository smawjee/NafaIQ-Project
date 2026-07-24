import { Link, useRouterState } from "@tanstack/react-router";
import { Menu, Sparkles, PanelLeft, PanelRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { usePermissions } from "@/hooks/use-permissions";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Logo } from "@/components/layout/Logo";
import { StockSearch } from "@/components/layout/StockSearch";
import { NotificationBell } from "@/components/layout/NotificationBell";
import { UserMenu } from "@/components/layout/UserMenu";
import { upgradeCta } from "@/components/layout/layout.utils";

export function Header({
  onMenu,
  collapsed,
  onExpand,
}: {
  onMenu: () => void;
  collapsed: boolean;
  onExpand: () => void;
}) {
  const { t, isUrdu } = useLang();
  const { theme, toggleTheme } = useLandingTheme();
  const isDark = theme === "dark";
  const { plan } = usePermissions();
  const cta = upgradeCta(plan);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const showStockSearch =
    pathname === "/psx" ||
    pathname.startsWith("/stock/") ||
    pathname === "/watchlist" ||
    pathname === "/portfolio" ||
    pathname === "/ai-insights";
  return (
    <header
      className={cn(
        "glass-chrome sticky top-0 z-20 flex h-[52px] items-center gap-2 border-b border-border px-3 sm:gap-3 lg:ps-6",
      )}
    >
      <button
        onClick={onMenu}
        className="text-text-secondary lg:hidden"
        aria-label={t("Open menu")}
      >
        <Menu className="h-5 w-5" strokeWidth={1.75} />
      </button>
      {collapsed && (
        <button
          onClick={onExpand}
          className="hidden text-text-secondary transition-colors hover:text-text-primary lg:inline-flex"
          aria-label="Show menu"
        >
          {isUrdu ? (
            <PanelRight className="h-5 w-5" strokeWidth={1.75} />
          ) : (
            <PanelLeft className="h-5 w-5" strokeWidth={1.75} />
          )}
        </button>
      )}
      <div className={cn("lg:hidden", collapsed && "lg:block")}>
        <Logo />
      </div>

      {/* Stock search only appears in market/investment contexts. */}
      {showStockSearch && <StockSearch />}

      {/* spacer pushes the utility cluster flush to the right edge */}
      <div className="flex-1" />

      {/* utility cluster — evenly spaced, right-aligned */}
      <div className="flex shrink-0 items-center gap-2">
        {cta.show && (
          <>
            <Link
              to="/plans"
              className="hidden h-9 shrink-0 items-center gap-1.5 rounded-[9px] border border-bull/40 bg-bull/10 px-3 text-[12px] font-semibold text-bull transition hover:border-bull/60 hover:bg-bull/15 sm:inline-flex"
            >
              <Sparkles className="h-3.5 w-3.5" /> {t(cta.label)}
            </Link>
            <Link
              to="/plans"
              aria-label={cta.label}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[9px] border border-bull/40 bg-bull/10 text-bull sm:hidden"
            >
              <Sparkles className="h-4 w-4" />
            </Link>
          </>
        )}
        <ThemeToggle isDark={isDark} onToggle={toggleTheme} />
        <NotificationBell />
        <UserMenu />
      </div>
    </header>
  );
}
