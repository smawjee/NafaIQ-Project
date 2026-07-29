import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import { LogOut, X, Sparkles } from "lucide-react";
import { useState } from "react";
import { usePersistedBool } from "@/hooks/use-persisted-bool";
import { motion, AnimatePresence, PageTransition } from "@/components/shared/animations";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { usePermissions } from "@/hooks/use-permissions";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { DemoBanner } from "@/components/demo/DemoBanner";
import { useLang } from "@/hooks/use-lang";
import { usePlatformFlags } from "@/hooks/use-platform-flags";
import { ScrollToTop } from "@/components/shared/ScrollToTop";
import { NAV } from "@/components/layout/layout.data";
import { initial, upgradeCta } from "@/components/layout/layout.utils";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { BottomNav } from "@/components/layout/BottomNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  const [collapsed, toggleCollapsed] = usePersistedBool("nafaiq-sidebar-collapsed");
  const { profile, user, signOut } = useAuth();
  const { plan } = usePermissions();
  const cta = upgradeCta(plan);
  const { theme } = useLandingTheme();
  const { t, isUrdu } = useLang();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  async function handleSignOut() {
    setDrawer(false);
    await signOut();
    navigate({ to: "/auth" });
  }
  return (
    <div
      dir={isUrdu ? "rtl" : "ltr"}
      className={cn(
        "relative min-h-screen overflow-x-hidden bg-background",
        theme === "light" && "theme-light landing-light",
        isUrdu && "font-urdu",
      )}
    >
      {/* ambient depth — very subtle brand wash */}
      <div className="ambient-glow -top-40 right-[-12%] h-[420px] w-[420px] bg-primary/[0.03]" />

      {!collapsed && <Sidebar onCollapse={() => toggleCollapsed(true)} />}
      <div className={cn("relative", !collapsed && "lg:ps-[260px]")}>
        <Header
          onMenu={() => setDrawer(true)}
          collapsed={collapsed}
          onExpand={() => toggleCollapsed(false)}
        />
        <Breadcrumbs />
        <MaintenanceBanner />
        <DemoBanner />
        <main
          className={cn(
            "pt-4 pb-24 lg:pb-8",
            pathname.startsWith("/learn/lesson") ? "px-0" : "px-3 sm:px-5 lg:px-6",
          )}
        >
          <PageTransition routeKey={pathname}>{children}</PageTransition>
        </main>
      </div>
      <BottomNav />
      <ScrollToTop />

      <AnimatePresence>
        {drawer && (
          <motion.div
            className="fixed inset-0 z-50 lg:hidden"
            onClick={() => setDrawer(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <motion.div
              className="glass-chrome safe-bottom absolute right-0 bottom-0 left-0 rounded-t-2xl border-t border-white/10 p-4"
              onClick={(e) => e.stopPropagation()}
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold text-text-primary">{t("More")}</span>
                <button onClick={() => setDrawer(false)}>
                  <X className="h-5 w-5 text-text-secondary" />
                </button>
              </div>
              {NAV.slice(5).map((n) => (
                <Link
                  key={n.to}
                  to={n.to}
                  onClick={() => setDrawer(false)}
                  className="flex items-center gap-3 rounded-[6px] px-3 py-3 text-sm text-text-primary hover:bg-hover"
                >
                  <n.icon className="h-5 w-5 text-text-secondary" />
                  {t(n.label)}
                </Link>
              ))}
              {cta.show && (
                <Link
                  to="/plans"
                  onClick={() => setDrawer(false)}
                  className="flex items-center gap-3 rounded-[6px] border border-bull/40 bg-bull/10 px-3 py-3 text-sm font-semibold text-bull hover:bg-bull/15"
                >
                  <Sparkles className="h-5 w-5" /> {t(cta.label)}
                </Link>
              )}
              <div className="mt-2 flex items-center gap-3 border-t border-border px-3 pt-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-bull/20 text-sm font-semibold text-bull">
                  {initial(profile?.display_name, user?.email)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-text-primary">
                    {profile?.display_name || user?.email?.split("@")[0] || "User"}
                  </div>
                  <div className="text-xs text-text-muted">{profile?.plan ?? "Free"} plan</div>
                </div>
                <button
                  onClick={handleSignOut}
                  className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1.5 text-sm font-medium text-bear hover:bg-hover"
                >
                  <LogOut className="h-4 w-4" /> {t("Sign out")}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * Shown while an administrator has `maintenance_mode` on.
 *
 * The backend already 503s every /api route in that state, so without this the
 * app just looks broken — every panel would show its own generic error. This
 * turns a wall of failures into one explained state.
 */
function MaintenanceBanner() {
  const { maintenanceMode } = usePlatformFlags();
  const { t } = useLang();
  if (!maintenanceMode) return null;
  return (
    <div
      role="status"
      className="mx-3 mt-3 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm text-warning sm:mx-5 lg:mx-6"
    >
      {t(
        "NafaIQ is undergoing scheduled maintenance. Some data may be unavailable until it completes.",
      )}
    </div>
  );
}
