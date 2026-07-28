/**
 * The admin console frame: collapsible sidebar, sticky command bar, mobile
 * drawer, and the `.admin-root` scope that activates the console's theme.
 *
 * Navigation is driven entirely by ADMIN_NAV and filtered by the caller's
 * permissions, so an admin never sees a link they cannot open.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  ArrowLeft,
  ChevronLeft,
  Languages,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { useAdmin } from "@/features/admin/data/useAdmin";
import { ADMIN_NAV, findNavItem, type AdminNavItem } from "@/features/admin/data/nav";
import { Avatar, IconButton, Kbd, RoleBadge, SectionLabel } from "./primitives";
import { CommandPalette, useCommandPalette } from "./CommandPalette";

const COLLAPSE_KEY = "nafaiq.admin.sidebar.collapsed";

/* -------------------------------------------------------------------------- */

function NavLinks({ collapsed, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const { can } = useAdmin();
  const { t } = useLang();
  const path = useRouterState({ select: (s) => s.location.pathname });

  const isActive = (item: AdminNavItem) =>
    item.exact ? path === item.to : path === item.to || path.startsWith(item.to + "/");

  return (
    <nav aria-label={t("Admin sections")} className="space-y-5">
      {ADMIN_NAV.map((section) => {
        const visible = section.items.filter((i) => can(i.permission));
        if (visible.length === 0) return null;
        return (
          <div key={section.label} className="space-y-0.5">
            {collapsed ? (
              <div className="mx-3 mb-1.5 h-px bg-border" aria-hidden />
            ) : (
              <SectionLabel className="px-3 pb-1">{t(section.label)}</SectionLabel>
            )}

            {visible.map((item) => {
              const active = isActive(item);
              const link = (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  title={collapsed ? t(item.label) : undefined}
                  className={cn(
                    "group relative flex items-center rounded-lg text-sm font-medium",
                    "transition-all duration-150 ease-out",
                    collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2",
                    active
                      ? "bg-primary/12 text-primary"
                      : "text-text-secondary hover:bg-hover hover:text-text-primary",
                  )}
                >
                  {/* Active rail — a shape cue in addition to the colour change. */}
                  <span
                    aria-hidden
                    className={cn(
                      "absolute start-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-e-full bg-primary transition-opacity duration-150",
                      active ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                  {!collapsed && <span className="truncate">{t(item.label)}</span>}
                </Link>
              );

              if (!collapsed) return link;
              return (
                <Tooltip.Root key={item.to} delayDuration={200}>
                  <Tooltip.Trigger asChild>{link}</Tooltip.Trigger>
                  <Tooltip.Portal>
                    <Tooltip.Content
                      side="right"
                      sideOffset={8}
                      className="admin-root z-50 rounded-lg border border-border bg-popover px-2.5 py-1.5 text-xs font-medium text-text-primary shadow-[var(--admin-elev-3)]"
                    >
                      {t(item.label)}
                    </Tooltip.Content>
                  </Tooltip.Portal>
                </Tooltip.Root>
              );
            })}
          </div>
        );
      })}
    </nav>
  );
}

/* -------------------------------------------------------------------------- */

function Brand({ collapsed }: { collapsed?: boolean }) {
  const { t } = useLang();
  return (
    <div className={cn("flex items-center gap-2.5", collapsed && "justify-center")}>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/25 bg-primary/12">
        <ShieldCheck className="h-4 w-4 text-primary" aria-hidden />
      </span>
      {!collapsed && (
        <span className="min-w-0">
          <span className="block text-sm font-bold leading-tight text-text-primary">
            {t("NafaIQ Admin")}
          </span>
          <span className="block truncate text-[11px] leading-tight text-text-muted">
            {t("Operations console")}
          </span>
        </span>
      )}
    </div>
  );
}

function UserMenu() {
  const { user, signOut } = useAuth();
  const { roles } = useAdmin();
  const { t, isUrdu } = useLang();
  const navigate = useNavigate();

  return (
    <DropdownMenu.Root dir={isUrdu ? "rtl" : "ltr"}>
      <DropdownMenu.Trigger asChild>
        <button
          className="flex cursor-pointer items-center gap-2 rounded-lg p-1 transition-colors hover:bg-hover"
          aria-label={t("Account menu")}
        >
          <Avatar email={user?.email} size="md" />
          <span className="hidden min-w-0 text-start sm:block">
            <span className="block max-w-[12rem] truncate text-xs font-medium text-text-primary">
              {user?.email}
            </span>
            <span className="block truncate text-[11px] text-text-muted">
              {roles.join(", ") || "admin"}
            </span>
          </span>
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="admin-root z-50 w-60 rounded-xl border border-border bg-popover p-1.5 shadow-[var(--admin-elev-3)]"
        >
          <div className="px-2 py-2">
            <div className="truncate text-xs font-medium text-text-primary">{user?.email}</div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {roles.length > 0 ? (
                roles.map((r) => <RoleBadge key={r} role={r} />)
              ) : (
                <span className="text-[11px] text-text-muted">{t("No roles")}</span>
              )}
            </div>
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-border" />
          <DropdownMenu.Item
            onSelect={() => navigate({ to: "/app" })}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-text-secondary outline-none data-[highlighted]:bg-hover data-[highlighted]:text-text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> {t("Back to app")}
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onSelect={() => void signOut()}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-bear outline-none data-[highlighted]:bg-bear/10"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden /> {t("Sign out")}
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/* -------------------------------------------------------------------------- */

export function AdminShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { t, lang, setLang, isUrdu } = useLang();
  const { theme, toggleTheme } = useLandingTheme();
  const [drawer, setDrawer] = useState(false);
  const palette = useCommandPalette();

  const [collapsed, setCollapsed] = useState(false);
  // Read the persisted preference after mount so SSR markup and the first
  // client render agree (avoids a hydration mismatch on the sidebar width).
  useEffect(() => {
    setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);
  function toggleCollapsed() {
    setCollapsed((v) => {
      window.localStorage.setItem(COLLAPSE_KEY, v ? "0" : "1");
      return !v;
    });
  }

  // Close the mobile drawer on navigation — otherwise it covers the page the
  // admin just asked for.
  useEffect(() => {
    setDrawer(false);
  }, [path]);

  // Mark <html> while the console is mounted. This is what lets the console's
  // token block reach PORTALLED surfaces — the sonner Toaster and the shared
  // ConfirmDialog are mounted once at the app root, outside `.admin-root`, so
  // without this every toast and confirmation dialog inside /admin would render
  // in the main app's palette. Cleaned up on unmount so leaving /admin restores
  // the app's own theme immediately.
  //
  // The original `dir` is captured here (mount-only) so it can be restored
  // exactly, even after the admin has toggled language several times.
  useEffect(() => {
    const root = document.documentElement;
    const originalDir = root.getAttribute("dir");
    root.setAttribute("data-admin-console", "");
    return () => {
      root.removeAttribute("data-admin-console");
      if (originalDir === null) root.removeAttribute("dir");
      else root.setAttribute("dir", originalDir);
    };
  }, []);

  // Direction has to live on <html>, not just the console wrapper.
  // Every drawer, dropdown, tooltip and the command palette render through a
  // Radix portal attached to document.body — outside the wrapper — so a `dir`
  // set only on the wrapper would leave all of them laid out LTR while the rest
  // of the console mirrored. Logical properties resolve against the element's
  // inherited direction, so setting it at the root fixes portals and page alike.
  useEffect(() => {
    document.documentElement.setAttribute("dir", isUrdu ? "rtl" : "ltr");
  }, [isUrdu]);

  const current = findNavItem(path);

  return (
    <Tooltip.Provider>
      {/* `admin-root` scopes the console's design tokens; `admin-ambient`
          paints the emerald wash and is applied only here, never on the
          portalled surfaces that also carry `admin-root`.

          `dir` is set here rather than on <html> so switching to Urdu flips the
          console's layout without disturbing the rest of the app. Every layout
          rule in the console uses logical properties (start/end, ps/pe, ms/me),
          so the whole thing mirrors from this one attribute. */}
      <div
        dir={isUrdu ? "rtl" : "ltr"}
        className={cn("admin-root admin-ambient min-h-screen", isUrdu && "font-urdu")}
      >
        <a
          href="#admin-main"
          className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
        >
          {t("Skip to content")}
        </a>

        {/* Desktop sidebar */}
        <aside
          className={cn(
            "admin-glass fixed inset-y-0 start-0 z-30 hidden flex-col border-e border-border lg:flex",
            "transition-[width] duration-200 ease-out",
            collapsed ? "w-[4.5rem]" : "w-64",
          )}
        >
          <div
            className={cn(
              "flex h-14 shrink-0 items-center border-b border-border",
              collapsed ? "justify-center px-2" : "px-4",
            )}
          >
            <Brand collapsed={collapsed} />
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
            <NavLinks collapsed={collapsed} />
          </div>

          <div className="shrink-0 border-t border-border p-3">
            <button
              onClick={toggleCollapsed}
              aria-label={collapsed ? t("Expand sidebar") : t("Collapse sidebar")}
              aria-expanded={!collapsed}
              className={cn(
                "flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium",
                "text-text-muted transition-colors hover:bg-hover hover:text-text-primary",
                collapsed && "justify-center px-0",
              )}
            >
              {collapsed ? (
                <PanelLeftOpen className="h-4 w-4" aria-hidden />
              ) : (
                <>
                  <PanelLeftClose className="h-4 w-4" aria-hidden /> {t("Collapse")}
                </>
              )}
            </button>
          </div>
        </aside>

        {/* Mobile drawer */}
        {drawer && (
          <div
            className="fixed inset-0 z-50 lg:hidden"
            role="dialog"
            aria-modal="true"
            aria-label={t("Admin sections")}
          >
            <button
              className="absolute inset-0 h-full w-full cursor-default bg-black/60 backdrop-blur-sm"
              onClick={() => setDrawer(false)}
              aria-label={t("Close navigation")}
              tabIndex={-1}
            />
            <div className="absolute inset-y-0 start-0 flex w-72 flex-col border-e border-border bg-card shadow-[var(--admin-elev-3)]">
              <div className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4">
                <Brand />
                <IconButton
                  label={t("Close navigation")}
                  size="sm"
                  onClick={() => setDrawer(false)}
                >
                  <X className="h-4 w-4" />
                </IconButton>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
                <NavLinks onNavigate={() => setDrawer(false)} />
              </div>
              <div className="shrink-0 border-t border-border p-3">
                <button
                  onClick={() => navigate({ to: "/app" })}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-hover hover:text-text-primary"
                >
                  <ArrowLeft className="h-4 w-4" aria-hidden /> {t("Back to app")}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main column */}
        <div
          className={cn(
            "transition-[padding] duration-200 ease-out",
            collapsed ? "lg:ps-[4.5rem]" : "lg:ps-64",
          )}
        >
          <header className="admin-glass sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border px-4">
            <IconButton
              label={t("Open navigation")}
              size="sm"
              className="lg:hidden"
              onClick={() => setDrawer(true)}
            >
              <Menu className="h-4 w-4" />
            </IconButton>

            {/* Current section — the breadcrumb trail lives in the page header,
                this is the persistent "you are here" anchor. */}
            {current && (
              <span className="hidden items-center gap-2 text-sm font-medium text-text-primary sm:flex">
                <current.icon className="h-4 w-4 text-text-muted" aria-hidden />
                {t(current.label)}
              </span>
            )}

            <button
              onClick={() => palette.setOpen(true)}
              className={cn(
                "ms-auto flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface-alt px-2.5",
                "text-sm text-text-muted transition-colors hover:border-border-hover hover:text-text-secondary",
                "sm:w-64 sm:justify-start",
              )}
              aria-label={t("Open command palette")}
            >
              <Search className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span className="hidden sm:inline">{t("Search…")}</span>
              <span className="ms-auto hidden items-center gap-0.5 sm:flex">
                <Kbd>⌘</Kbd>
                <Kbd>K</Kbd>
              </span>
            </button>

            {/* Language + theme live in the console's own header so an admin
                never has to leave /admin to change them. Both write to the same
                stores the main app uses, so the preference carries across. */}
            <IconButton
              label={t("Toggle language")}
              size="sm"
              onClick={() => setLang(lang === "ur" ? "en" : "ur")}
            >
              <span className="relative">
                <Languages className="h-4 w-4" aria-hidden />
                <span className="absolute -bottom-1.5 start-1/2 -translate-x-1/2 rtl:translate-x-1/2 text-[8px] font-bold uppercase leading-none text-primary">
                  {lang}
                </span>
              </span>
            </IconButton>

            <ThemeToggle
              isDark={theme === "dark"}
              onToggle={toggleTheme}
              label={t("Toggle theme")}
              className="h-8 w-8"
            />

            <UserMenu />
          </header>

          <main id="admin-main" className="mx-auto max-w-[100rem] px-4 py-6 sm:px-6">
            {children}
          </main>
        </div>

        <CommandPalette open={palette.open} onOpenChange={palette.setOpen} />
      </div>
    </Tooltip.Provider>
  );
}

/** Back link used by detail pages. Kept here so the affordance is consistent. */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 text-sm text-text-muted transition-colors hover:text-text-primary"
    >
      <ChevronLeft className="h-4 w-4 rtl:rotate-180" aria-hidden />
      {children}
    </Link>
  );
}
