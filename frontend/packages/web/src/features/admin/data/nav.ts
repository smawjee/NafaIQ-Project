/**
 * Single source of truth for the admin information architecture.
 *
 * The sidebar, the command palette and the breadcrumb helper all read this, so
 * a new admin surface is registered in exactly one place and can never appear
 * in navigation without a permission gate.
 */
import type { ComponentType } from "react";
import {
  Activity,
  Bell,
  Bug,
  Bot,
  Database,
  Flag,
  LayoutDashboard,
  LineChart,
  ScrollText,
  ShieldCheck,
  Users,
  LifeBuoy,
  Wallet,
} from "lucide-react";

export interface AdminNavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  /** Permission slug required to see *and* reach this surface. */
  permission: string;
  /** Match the path exactly (used for the index route). */
  exact?: boolean;
  description?: string;
}

export interface AdminNavSection {
  label: string;
  items: AdminNavItem[];
}

export const ADMIN_NAV: AdminNavSection[] = [
  {
    label: "Overview",
    items: [
      {
        to: "/admin",
        label: "Dashboard",
        icon: LayoutDashboard,
        permission: "overview.read",
        exact: true,
        description: "Platform snapshot and recent admin activity",
      },
    ],
  },
  {
    label: "People",
    items: [
      {
        to: "/admin/users",
        label: "Users",
        icon: Users,
        permission: "users.read",
        description: "Search, inspect, suspend and re-tier accounts",
      },
      {
        to: "/admin/roles",
        label: "Roles & Access",
        icon: ShieldCheck,
        permission: "roles.read",
        description: "Administrators, roles and permission mapping",
      },
      {
        to: "/admin/subscriptions",
        label: "Subscriptions",
        icon: Wallet,
        permission: "users.tier.read",
        description: "Plan distribution and tier management",
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
        description: "PSX ingestion pipeline health",
      },
      {
        to: "/admin/signals",
        label: "Signals",
        icon: LineChart,
        permission: "signals.read",
        description: "Model registry and computed-table volumes",
      },
      {
        to: "/admin/ai",
        label: "AI Operations",
        icon: Bot,
        permission: "ai.read",
        description: "Assistant, LearnHub and report usage",
      },
      {
        to: "/admin/alerts",
        label: "Alerts",
        icon: Bell,
        permission: "alerts.read",
        description: "Price and app alert volumes and delivery health",
      },
    ],
  },
  {
    label: "Reliability",
    items: [
      {
        to: "/admin/errors",
        label: "Errors",
        icon: Bug,
        permission: "errors.read",
        description: "Automatically captured client and server failures",
      },
      {
        to: "/admin/bug-reports",
        label: "Bug Reports",
        icon: LifeBuoy,
        permission: "support.read",
        description: "Problems users reported themselves",
      },
    ],
  },
  {
    label: "Platform",
    items: [
      {
        to: "/admin/flags",
        label: "Feature Flags",
        icon: Flag,
        permission: "flags.read",
        description: "Runtime platform switches",
      },
      {
        to: "/admin/audit",
        label: "Audit Log",
        icon: ScrollText,
        permission: "audit.read",
        description: "Append-only record of every admin action",
      },
      {
        to: "/admin/system",
        label: "System Health",
        icon: Activity,
        permission: "system.read",
        description: "Database, scheduler and deployment status",
      },
    ],
  },
];

/** Flat lookup used for breadcrumbs and the command palette. */
export const ADMIN_NAV_ITEMS: AdminNavItem[] = ADMIN_NAV.flatMap((s) => s.items);

export function findNavItem(pathname: string): AdminNavItem | undefined {
  return ADMIN_NAV_ITEMS.filter((i) =>
    i.exact ? pathname === i.to : pathname === i.to || pathname.startsWith(i.to + "/"),
  ).sort((a, b) => b.to.length - a.to.length)[0];
}
