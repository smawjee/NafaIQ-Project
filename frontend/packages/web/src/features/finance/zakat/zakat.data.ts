export const NISAB = 135000; // PKR — silver-based nisab threshold
export const ZAKAT_RATE = 0.025;

export interface ZakatLine {
  key: string;
  label: string;
  sub: string;
}

export const ASSET_LINES: ZakatLine[] = [
  { key: "cash", label: "Cash & Bank Balance", sub: "Linked bank accounts" },
  { key: "gold", label: "Gold & Jewelry", sub: "Self-reported" },
  { key: "stocks", label: "Stocks (PSX)", sub: "Portfolio" },
  { key: "funds", label: "Mutual Funds", sub: "Portfolio" },
  { key: "business", label: "Business Inventory", sub: "Self-reported" },
  { key: "property", label: "Property (non-primary)", sub: "Self-reported" },
];

export const LIABILITY_LINES: ZakatLine[] = [
  { key: "loans", label: "Outstanding Loans", sub: "Self-reported" },
  { key: "credit", label: "Credit Card Debt", sub: "Self-reported" },
];

export const ZAKAT_DEFAULTS: Record<string, number> = {
  cash: 850000,
  gold: 420000,
  stocks: 4250000,
  funds: 500000,
  business: 0,
  property: 0,
  loans: 200000,
  credit: 45000,
};
