import { MONTHS } from "@/features/portfolio/portfolio.data";

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
