import { MONTHS } from "@/features/portfolio/portfolio.data";

/** Add/Edit holding form state. Cost basis is entered as a per-share price OR a
 *  total amount paid; `costMode` picks which field is authoritative. */
export interface HoldingForm {
  ticker: string;
  sector: string;
  shares: string;
  costMode: "per_share" | "total";
  buyPrice: string;
  totalCost: string;
  current: string;
}

export const EMPTY_HOLDING_FORM: HoldingForm = {
  ticker: "",
  sector: "",
  shares: "",
  costMode: "per_share",
  buyPrice: "",
  totalCost: "",
  current: "",
};

// Synthetic showcase history seeded from the store's invested amount, so the
// demo chart tracks demo buys/sells.
export function series(n: number, base: number) {
  return MONTHS.slice(12 - n).map((label, i, a) => {
    const f = i / (a.length - 1 || 1);
    return {
      label,
      value: Math.round(base * (1 + 0.1273 * f)),
      benchmark: Math.round(base * (1 + 0.095 * f)),
    };
  });
}

export function relativeBenchmarkDiff(data: { value: number; benchmark: number }[]) {
  if (data.length < 2) return null;
  const first = data[0];
  const last = data[data.length - 1];
  if (!first || !last || first.value <= 0 || first.benchmark <= 0) return null;
  const portfolioPct = ((last.value - first.value) / first.value) * 100;
  const benchmarkPct = ((last.benchmark - first.benchmark) / first.benchmark) * 100;
  return portfolioPct - benchmarkPct;
}
