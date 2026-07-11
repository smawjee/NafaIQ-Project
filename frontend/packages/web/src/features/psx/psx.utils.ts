import { STOCKS } from "@/lib/data";

export function tfDays(tf: string) {
  return { "1D": 5, "1W": 14, "1M": 30, "3M": 90, "6M": 130, "1Y": 250, All: 250 }[tf] ?? 250;
}

export function symbolMeta(sym: string) {
  if (sym === "KSE-100") return { seed: 1, start: 65000, end: 78542.1, vMin: 200, vMax: 800 };
  const s = STOCKS[sym];
  return { seed: s.seed, start: s.start, end: s.price, vMin: 100, vMax: 600 };
}
