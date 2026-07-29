export const ZAKAT_RATE = 0.025;
export const GOLD_NISAB_TOLA = 7.5;
export const SILVER_NISAB_TOLA = 52.5;

export interface ZakatLine {
  key: string;
  label: string;
  sub: string;
}

export const ASSET_LINES: ZakatLine[] = [
  { key: "cash", label: "Cash & Bank Balance", sub: "Enter your current cash and bank balance" },
  { key: "gold", label: "Gold & Jewelry", sub: "Enter gold weight in tola" },
  { key: "silver", label: "Silver", sub: "Enter silver weight in tola" },
  { key: "stocks", label: "Stocks (PSX)", sub: "Live portfolio value, editable" },
  { key: "funds", label: "Mutual Funds", sub: "Enter current redeemable value" },
  { key: "business", label: "Business Inventory", sub: "Self-reported" },
  { key: "receivables", label: "Receivables", sub: "Money owed to you" },
  { key: "property", label: "Property (non-primary)", sub: "Self-reported" },
];

export const LIABILITY_LINES: ZakatLine[] = [
  { key: "loans", label: "Outstanding Loans", sub: "Self-reported" },
  { key: "credit", label: "Credit Card Debt", sub: "Self-reported" },
];

export const ZAKAT_DEFAULTS: Record<string, number> = {
  cash: 0,
  gold: 0,
  silver: 0,
  stocks: 0,
  funds: 0,
  business: 0,
  receivables: 0,
  property: 0,
  loans: 0,
  credit: 0,
};
