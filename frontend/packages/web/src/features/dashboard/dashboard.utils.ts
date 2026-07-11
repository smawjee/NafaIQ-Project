import { WEEKDAYS, MONTHS } from "./dashboard.data";

// Synthetic showcase history ending at the store's current portfolio value,
// so the demo chart stays consistent with the live demo KPIs.
export function portfolioSeries(months: number, endValue: number) {
  const base = endValue / 1.1273;
  const out = [];
  const labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"].slice(6 - months);
  for (let i = 0; i < labels.length; i++) {
    const f = i / (labels.length - 1 || 1);
    out.push({
      label: labels[i],
      value: Math.round(base * (1 + 0.1273 * f + Math.sin(i) * 0.01)),
      benchmark: Math.round(base * (1 + 0.095 * f + Math.cos(i) * 0.008)),
    });
  }
  return out;
}

export function formatToday() {
  const d = new Date();
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}
