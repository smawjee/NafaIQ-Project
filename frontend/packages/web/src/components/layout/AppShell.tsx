import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import logo from "@/assets/logo.png";
import {
  LayoutDashboard,
  TrendingUp,
  Briefcase,
  Wallet,
  GraduationCap,
  Bell,
  LogOut,
  Menu,
  X,
  Search,
  Sparkles,
  User,
  Settings,
  CreditCard,
  ChevronRight,
  PanelLeftClose,
  PanelRightClose,
  PanelLeft,
  PanelRight,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence, PageTransition } from "@/components/shared/animations";
import { cn } from "@/lib/utils";
import { TICKER_ITEMS, STOCKS } from "@/lib/data";
import { LEARNING_PATHS, LESSON_CONTENT } from "@/lib/learn/data";
import { useAuth } from "@/hooks/use-auth";
import { useLandingTheme } from "@/hooks/use-landing-theme";
import { useLang } from "@/hooks/use-lang";
import { useNotifications, useMarkNotificationRead } from "@/hooks/use-notifications";
import { ScrollToTop } from "@/components/shared/ScrollToTop";
import { ThemeToggle } from "@/components/shared/ThemeToggle";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, mobile: "Home" },
  { to: "/psx", label: "PSX Market", icon: TrendingUp, mobile: "Markets" },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase, mobile: "Portfolio" },
  { to: "/finance", label: "Finance", icon: Wallet, mobile: "Finance" },
  { to: "/learn", label: "Learn Hub", icon: GraduationCap, mobile: "Learn" },
  { to: "/alerts", label: "Alerts", icon: Bell },
] as const;

const PRIMARY_NAV = NAV.slice(0, 6);

const NOTIFICATIONS = [
  { id: 1, title: "HBL flashed a Strong Buy", time: "2m ago", tone: "bull" },
  { id: 2, title: "Dining budget exceeded by 15%", time: "1h ago", tone: "warning" },
  { id: 3, title: "KSE-100 up 1.24% — market open", time: "Today", tone: "bull" },
] as const;

const LABELS: Record<string, string> = {
  app: "Dashboard",
  psx: "PSX Market",
  portfolio: "Portfolio",
  finance: "Finance",
  learn: "Learn Hub",
  alerts: "Alerts",
  stock: "Markets",
  lesson: "Lesson",
};

function Logo({ to = "/app" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2">
      <img src={logo} alt="NafaIQ" width={28} height={28} className="rounded-[6px]" />
      <span className="font-display text-lg font-bold tracking-tight text-text-primary">
        Nafa<span className="text-primary">IQ</span>
      </span>
    </Link>
  );
}

function initial(name?: string | null, email?: string | null) {
  return (name?.trim()?.[0] || email?.trim()?.[0] || "U").toUpperCase();
}

function SidebarLink({
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

function Sidebar({ onCollapse }: { onCollapse: () => void }) {
  const { t, isUrdu } = useLang();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { profile, user, signOut } = useAuth();
  const navigate = useNavigate();
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  async function handleSignOut() {
    await signOut();
    navigate({ to: "/auth" });
  }
  const isActive = (to: string) => path === to || path.startsWith(to + "/");
  return (
    <aside className="glass-chrome fixed top-0 start-0 z-30 hidden h-screen w-[212px] flex-col border-e border-white/[0.06] shadow-[1px_0_0_rgba(255,255,255,0.02),4px_0_24px_rgba(0,0,0,0.25)] lg:flex">
      <div className="flex h-[56px] items-center border-b border-white/[0.06] px-5">
        <Logo />
      </div>

      {/* primary navigation — spacing below logo */}
      <nav className="flex-1 space-y-1 px-3 pt-5">
        {PRIMARY_NAV.map((n) => (
          <SidebarLink key={n.to} to={n.to} label={n.label} icon={n.icon} active={isActive(n.to)} />
        ))}
      </nav>

      {/* utility section — separated from primary nav */}
      <div className="space-y-1 border-t border-white/[0.06] px-3 py-3">
        <SidebarLink
          to="/settings"
          label="Settings"
          icon={Settings}
          active={isActive("/settings")}
        />
        <button
          onClick={onCollapse}
          aria-label={t("Collapse sidebar")}
          className="group flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13px] font-medium text-text-secondary transition-colors duration-200 hover:bg-white/[0.04] hover:text-text-primary"
        >
          {isUrdu ? (
            <PanelRightClose
              className="h-5 w-5 shrink-0 text-text-muted group-hover:text-text-primary"
              strokeWidth={1.75}
            />
          ) : (
            <PanelLeftClose
              className="h-5 w-5 shrink-0 text-text-muted group-hover:text-text-primary"
              strokeWidth={1.75}
            />
          )}
          {t("Collapse")}
        </button>
      </div>

      <div className="flex items-center gap-3 border-t border-white/[0.06] p-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
          {initial(profile?.display_name, user?.email)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium text-text-primary">{name}</div>
          <div className="text-[11px] text-text-muted">{profile?.plan ?? "Free"} plan</div>
        </div>
        <button
          onClick={handleSignOut}
          aria-label="Sign out"
          className="text-text-secondary transition-colors hover:text-bear"
        >
          <LogOut className="h-[18px] w-[18px]" strokeWidth={1.75} />
        </button>
      </div>
    </aside>
  );
}

function StockSearch() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const { t: tr } = useLang();
  function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = q.trim().toUpperCase();
    if (!t) return;
    if (STOCKS[t]) {
      navigate({ to: "/stock/$ticker", params: { ticker: t } });
    } else {
      navigate({ to: "/psx" });
    }
    setQ("");
  }
  return (
    <form onSubmit={submit} className="relative hidden w-full max-w-xs shrink-0 sm:block">
      <Search className="pointer-events-none absolute start-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={tr("Search stocks (e.g. HBL)…")}
        aria-label={tr("Search stocks")}
        className="h-8 w-full rounded-[8px] border border-white/[0.08] bg-surface ps-8 pe-3 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-bull"
      />
    </form>
  );
}

function NotificationBell() {
  const { t } = useLang();
  const { user } = useAuth();
  const isLoggedIn = !!user;
  const { data: apiNotifications } = useNotifications();
  const markRead = useMarkNotificationRead();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const display = isLoggedIn && apiNotifications ? apiNotifications : null;
  const unreadCount = display ? display.filter((n) => !n.read).length : NOTIFICATIONS.length;
  const items = display
    ? display.slice(0, 10).map((n) => ({
        id: String(n.id),
        title: n.title,
        time: new Date(n.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
        tone: n.kind === "price_alert" ? "bull" : "warning",
        read: n.read,
        link: n.link,
      }))
    : NOTIFICATIONS.map((n) => ({ ...n, link: null as string | null }));

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative text-text-secondary transition-colors hover:text-text-primary"
        aria-label={t("Notifications")}
      >
        <Bell className="h-[18px] w-[18px]" strokeWidth={1.75} />
        {unreadCount > 0 && (
          <span className="absolute -top-1.5 -end-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-bear px-1 text-[9px] font-bold text-white">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div
          className={cn(
            "glass-chrome absolute top-9 z-50 w-72 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[12px] border border-white/[0.08] shadow-2xl",
            "end-0",
          )}
        >
          <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
            <span className="text-[13px] font-semibold text-text-primary">
              {t("Notifications")}
            </span>
            <Link
              to="/alerts"
              onClick={() => setOpen(false)}
              className="text-[11px] text-bull hover:underline"
            >
              {t("View all")}
            </Link>
          </div>
          <ul className="max-h-72 overflow-y-auto">
            {items.length === 0 ? (
              <li className="px-4 py-6 text-center text-[12px] text-text-muted">
                {t("No notifications")}
              </li>
            ) : items.map((n) => (
              <li
                key={n.id}
                onClick={() => {
                  if (isLoggedIn && display) {
                    const orig = display.find((x) => String(x.id) === n.id);
                    if (orig && !orig.read) markRead.mutate(orig.id);
                    if (n.link) window.location.href = n.link;
                  }
                }}
                className="flex items-start gap-2.5 px-4 py-3 transition-colors hover:bg-white/[0.03] cursor-pointer"
              >
                <span
                  className={cn(
                    "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                    n.tone === "bull" ? "bg-bull" : "bg-warning",
                  )}
                />
                <div className="min-w-0">
                  <div className="text-[13px] text-text-primary">{n.title}</div>
                  <div className="text-[11px] text-text-muted">{n.time}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const { profile, user, signOut } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  async function handleSignOut() {
    setOpen(false);
    await signOut();
    navigate({ to: "/auth" });
  }
  const items = [
    { label: "Profile", icon: User, to: "/app" as const },
    { label: "Settings", icon: Settings, to: "/settings" as const },
    { label: "Plans / Upgrade", icon: CreditCard, to: "/plans" as const },
  ];
  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary transition hover:brightness-110"
        aria-label={t("User menu")}
      >
        {initial(profile?.display_name, user?.email)}
      </button>
      {open && (
        <div
          className={cn(
            "glass-chrome absolute top-9 z-50 w-56 max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[12px] border border-white/[0.08] shadow-2xl",
            "end-0",
          )}
        >
          <div className="border-b border-white/[0.06] px-4 py-3">
            <div className="truncate text-[13px] font-semibold text-text-primary">{name}</div>
            <div className="text-[11px] text-text-muted">{profile?.plan ?? "Free"} plan</div>
          </div>
          <nav className="p-1.5">
            {items.map((it) => (
              <Link
                key={it.label}
                to={it.to}
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-[8px] px-3 py-2 text-[13px] text-text-secondary transition hover:bg-white/[0.04] hover:text-text-primary"
              >
                <it.icon className="h-4 w-4" strokeWidth={1.75} />
                {t(it.label)}
              </Link>
            ))}
            <button
              onClick={handleSignOut}
              className="flex w-full items-center gap-2.5 rounded-[8px] px-3 py-2 text-[13px] text-bear transition hover:bg-bear/10"
            >
              <LogOut className="h-4 w-4" strokeWidth={1.75} /> {t("Logout")}
            </button>
          </nav>
        </div>
      )}
    </div>
  );
}

function Header({
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
  return (
    <header
      className={cn(
        "glass-chrome sticky top-0 z-20 flex h-[52px] items-center gap-2 border-b border-white/[0.06] px-3 sm:gap-3 lg:ps-6",
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

      {/* search anchored left at a fixed max-width */}
      <StockSearch />

      {/* spacer pushes the utility cluster flush to the right edge */}
      <div className="flex-1" />

      {/* utility cluster — evenly spaced, right-aligned */}
      <div className="flex shrink-0 items-center gap-3 sm:gap-4">
        <Link
          to="/plans"
          className="hidden shrink-0 items-center gap-1.5 rounded-[8px] border border-bull/40 bg-bull/10 px-3 py-1.5 text-[12px] font-semibold text-bull transition hover:border-bull/60 hover:bg-bull/15 sm:inline-flex"
        >
          <Sparkles className="h-3.5 w-3.5" /> {t("Upgrade to Pro")}
        </Link>
        <Link
          to="/plans"
          aria-label="Upgrade to Pro"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] border border-bull/40 bg-bull/10 text-bull sm:hidden"
        >
          <Sparkles className="h-4 w-4" />
        </Link>
        <ThemeToggle isDark={isDark} onToggle={toggleTheme} />
        <NotificationBell />
        <UserMenu />
      </div>
    </header>
  );
}

function Breadcrumbs() {
  const { t } = useLang();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const segments = path.split("/").filter(Boolean);
  if (segments.length < 2) return null;

  // Special-case lesson pages: /learn/lesson/$id -> Learn Hub > <Path> > <Lesson title>
  let crumbs: { href: string; label: string; last: boolean }[];
  if (segments[0] === "learn" && segments[1] === "lesson" && segments[2]) {
    const id = decodeURIComponent(segments[2]);
    const lesson = LESSON_CONTENT[id];
    const pathName = LEARNING_PATHS.find((p) => p.lessonIds.includes(id))?.title ?? "Lessons";
    crumbs = [
      { href: "/learn", label: "Learn Hub", last: false },
      { href: "/learn", label: pathName, last: false },
      {
        href: path,
        label: lesson?.title ?? id.toUpperCase(),
        last: true,
      },
    ];
  } else {
    crumbs = segments.map((seg, i) => {
      const href = "/" + segments.slice(0, i + 1).join("/");
      const isParam = !LABELS[seg];
      const label = isParam ? decodeURIComponent(seg).toUpperCase() : LABELS[seg];
      return { href, label, last: i === segments.length - 1 };
    });
  }
  return (
    <nav aria-label="Breadcrumb" className="border-b border-white/[0.04] px-3 py-2 sm:px-5 lg:px-6">
      <ol className="mx-auto flex max-w-7xl items-center gap-1.5 text-[12px]">
        {crumbs.map((c, i) => (
          <li key={c.href} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-3 w-3 text-text-muted" />}
            {c.last ? (
              <span className="font-medium text-text-primary">{t(c.label)}</span>
            ) : (
              <span className="text-text-secondary">{t(c.label)}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function BottomNav() {
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

export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("nafaiq-sidebar-collapsed") === "1";
  });
  function toggleCollapsed(next: boolean) {
    setCollapsed(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("nafaiq-sidebar-collapsed", next ? "1" : "0");
    }
  }
  const { profile, user, signOut } = useAuth();
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
      <div className={cn("relative", !collapsed && "lg:ps-[212px]")}>
        <Header
          onMenu={() => setDrawer(true)}
          collapsed={collapsed}
          onExpand={() => toggleCollapsed(false)}
        />
        <Breadcrumbs />
        <main className={cn(
          "pt-4 pb-24 lg:pb-8",
          pathname.startsWith("/learn/lesson") ? "px-0" : "px-3 sm:px-5 lg:px-6",
        )}>
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
              <Link
                to="/plans"
                onClick={() => setDrawer(false)}
                className="flex items-center gap-3 rounded-[6px] border border-bull/40 bg-bull/10 px-3 py-3 text-sm font-semibold text-bull hover:bg-bull/15"
              >
                <Sparkles className="h-5 w-5" /> {t("Upgrade to Pro")}
              </Link>
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
