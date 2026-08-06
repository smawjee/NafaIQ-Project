export const CAT_COLOR: Record<string, string> = {
  Utilities: "#3b82f6",
  Income: "#00d4aa",
  "Food & Dining": "#f59e0b",
  Transport: "#8b5cf6",
  Groceries: "#00d4aa",
  Subscriptions: "#e5484d",
  Shopping: "#8b5cf6",
  Savings: "#6b7280",
};

export const CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Shopping",
  "Subscriptions",
  "Savings",
  "Income",
];

export const ACCOUNTS = [
  "HBL Current",
  "Meezan Debit",
  "Easypaisa",
  "Meezan Savings",
  "Allied Bank Card",
  "Cheque",
  "Cash",
  "Bank Transfer",
];

/**
 * `transactions.source` doubles as the payment method for anything the user
 * typed in, but the backend also writes three machine values there (see
 * `services/finance/payment_methods.py::SYSTEM_SOURCES`) to mark rows it
 * generated itself. Those are not payment methods and must not be offered as
 * one, nor printed raw — a stock purchase was rendering as "stock_trade".
 */
export const SYSTEM_SOURCES: Record<string, string> = {
  manual: "Manual",
  bank_email: "Bank email",
  stock_trade: "Stock trade",
};

export function isSystemSource(source: string | null | undefined): boolean {
  return !!source && source.trim().toLowerCase() in SYSTEM_SOURCES;
}

/** Display label for a transaction source; user-entered values pass through. */
export function sourceLabel(source: string | null | undefined): string {
  const clean = source?.trim();
  if (!clean) return SYSTEM_SOURCES.manual;
  return SYSTEM_SOURCES[clean.toLowerCase()] ?? clean;
}
