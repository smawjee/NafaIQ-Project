import { type ComponentType, type ReactNode, useState } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  ArrowLeft,
  Bot,
  Database,
  Flag,
  Gauge,
  LayoutDashboard,
  LineChart,
  Menu,
  ScrollText,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useAdmin } from "@/features/admin/data/useAdmin";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  permission: string;
  exact?: boolean;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [
      {
        to: "/admin",
        label: "Dashboard",
        icon: LayoutDashboard,
        permission: "overview.read",
        exact: true,
      },
    ],
  },
  {
    label: "People",
    items: [
      { to: "/admin/users", label: "Users", icon: Users, permission: "users.read" },
      { to: "/admin/roles", label: "Roles & Access", icon: ShieldCheck, permission: "roles.read" },
      {
        to: "/admin/subscriptions",
        label: "Subscriptions",
        icon: Gauge,
        permission: "users.tier.read",
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        to: "/admin/market-data",
        label: "Market Data",
        icon: Database,
        permission: "market_data.read",
      },
      { to: "/admin/signals", label: "Signals", icon: LineChart, permission: "signals.read" },
      { to: "/admin/ai", label: "AI Operations", icon: Bot, permission: "ai.read" },
    ],
  },
  {
    label: "Platform",
    items: [
      { to: "/admin/flags", label: "Feature Flags", icon: Flag, permission: "flags.read" },
      { to: "/admin/audit", label: "Audit Log", icon: ScrollText, permission: "audit.read" },
      { to: "/admin/system", label: "System Health", icon: Activity, permission: "system.read" },
    ],
  },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAdmin();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const isActive = (item: NavItem) =>
    item.exact ? path === item.to : path === item.to || path.startsWith(item.to + "/");

  return (
    <nav className="space-y-5">
      {SECTIONS.map((section) => {
        const visible = section.items.filter((i) => can(i.permission));
        if (visible.length === 0) return null;
        return (
          <div key={section.label} className="space-y-1">
            <div className="px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              {section.label}
            </div>
            {visible.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive(item)
                    ? "bg-primary/10 text-primary"
                    : "text-text-secondary hover:bg-hover hover:text-text-primary",
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            ))}
          </div>
        );
      })}
    </nav>
  );
}

export function AdminShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { roles } = useAdmin();
  const navigate = useNavigate();
  const [drawer, setDrawer] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 start-0 z-30 hidden w-64 flex-col border-e border-border bg-card/40 lg:flex">
        <div className="flex items-center gap-2 border-b border-border px-4 py-4">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <div className="min-w-0">
            <div className="text-sm font-bold text-text-primary">NafaIQ Admin</div>
            <div className="truncate text-[11px] text-text-muted">Operations console</div>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          <NavLinks />
        </div>
        <div className="border-t border-border px-3 py-3">
          <button
            onClick={() => navigate({ to: "/app" })}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-hover hover:text-text-primary"
          >
            <ArrowLeft className="h-4 w-4" /> Back to app
          </button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-50 lg:hidden" onClick={() => setDrawer(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div
            className="absolute inset-y-0 start-0 flex w-72 flex-col border-e border-border bg-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                <span className="text-sm font-bold text-text-primary">NafaIQ Admin</span>
              </div>
              <button onClick={() => setDrawer(false)} aria-label="Close menu">
                <X className="h-5 w-5 text-text-muted" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
              <NavLinks onNavigate={() => setDrawer(false)} />
            </div>
            <div className="border-t border-border px-3 py-3">
              <button
                onClick={() => navigate({ to: "/app" })}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-text-secondary hover:bg-hover"
              >
                <ArrowLeft className="h-4 w-4" /> Back to app
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main column */}
      <div className="lg:ps-64">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-border bg-background/80 px-4 py-3 backdrop-blur">
          <button className="lg:hidden" onClick={() => setDrawer(true)} aria-label="Open menu">
            <Menu className="h-5 w-5 text-text-primary" />
          </button>
          <div className="ms-auto flex items-center gap-3">
            <div className="hidden text-end sm:block">
              <div className="text-xs font-medium text-text-primary">{user?.email}</div>
              <div className="text-[11px] text-text-muted">{roles.join(", ") || "admin"}</div>
            </div>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
              {(user?.email ?? "A").slice(0, 1).toUpperCase()}
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </div>
    </div>
  );
}
