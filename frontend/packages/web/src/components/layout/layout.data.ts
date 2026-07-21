import {
  Bell,
  Banknote,
  Bookmark,
  BriefcaseBusiness,
  ChartCandlestick,
  CircleHelp,
  Coins,
  GraduationCap,
  House,
  Landmark,
  Settings,
  Sparkles,
  Wallet,
} from "lucide-react";

export const NAV = [
  { to: "/app", label: "Home", icon: House, mobile: "Home" },
  { to: "/psx", label: "PSX Market", icon: ChartCandlestick, mobile: "Markets" },
  { to: "/portfolio", label: "Portfolio", icon: BriefcaseBusiness, mobile: "Portfolio" },
  { to: "/finance", label: "Finance", icon: Wallet, mobile: "Finance" },
  { to: "/learn", label: "Learn Hub", icon: GraduationCap, mobile: "Learn" },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/funds", label: "Mutual Funds", icon: Landmark, mobile: "Funds" },
  { to: "/dividends", label: "Dividend Calculator", icon: Coins, mobile: "Dividends" },
  { to: "/monetary", label: "Monetary Desk", icon: Banknote, mobile: "Rates" },
] as const;

export const PRIMARY_NAV = NAV;

export const SIDEBAR_SECTIONS = [
  {
    label: "Overview",
    items: [
      { to: "/app", label: "Home", icon: House },
      { to: "/psx", label: "PSX Market", icon: ChartCandlestick },
    ],
  },
  {
    label: "Investments",
    items: [
      { to: "/portfolio", label: "Portfolio", icon: BriefcaseBusiness },
      { to: "/watchlist", label: "Watchlist", icon: Bookmark },
      { to: "/alerts", label: "Alerts", icon: Bell },
    ],
  },
  {
    label: "Finance",
    items: [{ to: "/finance", label: "Finance", icon: Wallet }],
  },
  {
    label: "AI",
    items: [{ to: "/ai-insights", label: "AI Insights", icon: Sparkles }],
  },
  {
    label: "Learning",
    items: [{ to: "/learn", label: "Learn Hub", icon: GraduationCap }],
  },
  {
    label: "Tools",
    items: [
      { to: "/dividends", label: "Dividend Calculator", icon: Coins },
      { to: "/funds", label: "Mutual Funds", icon: Landmark },
      { to: "/monetary", label: "Monetary Desk", icon: Banknote },
    ],
  },
] as const;

export const SIDEBAR_BOTTOM_NAV = [
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/help", label: "Help & Support", icon: CircleHelp },
] as const;

export const LABELS: Record<string, string> = {
  app: "Home",
  psx: "PSX Market",
  portfolio: "Portfolio",
  funds: "Mutual Funds",
  dividends: "Dividend Calculator",
  monetary: "Monetary Desk",
  finance: "Finance",
  learn: "Learn Hub",
  alerts: "Alerts",
  watchlist: "Watchlist",
  "ai-insights": "AI Insights",
  help: "Help & Support",
  stock: "Markets",
  lesson: "Lesson",
};
