import {
  LayoutDashboard,
  TrendingUp,
  Briefcase,
  Wallet,
  GraduationCap,
  Bell,
  PiggyBank,
  Banknote,
} from "lucide-react";

export const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, mobile: "Home" },
  { to: "/psx", label: "PSX Market", icon: TrendingUp, mobile: "Markets" },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase, mobile: "Portfolio" },
  { to: "/finance", label: "Finance", icon: Wallet, mobile: "Finance" },
  { to: "/learn", label: "Learn Hub", icon: GraduationCap, mobile: "Learn" },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/funds", label: "Mutual Funds", icon: PiggyBank, mobile: "Funds" },
  { to: "/dividends", label: "Dividends", icon: Banknote, mobile: "Dividends" },
] as const;

// Desktop sidebar renders the full nav — slicing here would silently hide any
// entry appended to NAV (as /funds and /dividends were). Mobile still uses
// BottomNav's first-5 slice plus the AppShell "More" drawer for the remainder.
export const PRIMARY_NAV = NAV;

export const LABELS: Record<string, string> = {
  app: "Dashboard",
  psx: "PSX Market",
  portfolio: "Portfolio",
  funds: "Mutual Funds",
  dividends: "Dividends",
  finance: "Finance",
  learn: "Learn Hub",
  alerts: "Alerts",
  stock: "Markets",
  lesson: "Lesson",
};
