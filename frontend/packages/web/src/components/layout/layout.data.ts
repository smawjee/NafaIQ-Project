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

export const PRIMARY_NAV = NAV.slice(0, 6);

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
