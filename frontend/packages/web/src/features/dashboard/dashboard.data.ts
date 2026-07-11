import { TrendingUp, Calendar, Wallet, Target } from "lucide-react";

export const RANGES = ["1M", "3M", "6M", "1Y"] as const;

export const WEEKDAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];
export const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export const TX_CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Shopping",
  "Subscriptions",
  "Savings",
  "Income",
];
export const TX_ACCOUNTS = ["HBL Current", "Meezan Debit", "Easypaisa", "Meezan Savings"];

export const ALERT_TYPES = [
  { label: "Stock Price", icon: TrendingUp, emoji: "🔔" },
  { label: "Bill Reminder", icon: Calendar, emoji: "📅" },
  { label: "Budget", icon: Wallet, emoji: "💸" },
  { label: "Goal Milestone", icon: Target, emoji: "🎯" },
];
export const ALERT_STOCKS = ["HBL", "ENGRO", "LUCK", "OGDC"];
