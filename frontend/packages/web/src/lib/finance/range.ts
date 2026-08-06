const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * Human label for one month key.
 *
 * The series carries two shapes: the API returns `YYYY-MM`, while the demo
 * fixture uses bare month names (`"Jan"`). Both reach this component, so both
 * are handled rather than assuming one and mislabelling the other.
 */
export function formatMonthKey(key: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(key);
  if (!match) return key;
  const monthIndex = Number(match[2]) - 1;
  const name = MONTHS[monthIndex];
  return name ? `${name} ${match[1]}` : key;
}

/**
 * Caption for a series of month keys, e.g. "Mar 2026 — Aug 2026".
 *
 * The Overview card used to hard-code `"Jan 2026 — Jun 2026"` — the demo
 * fixture's months — so a real user read a caption that disagreed with the axis
 * directly beneath it. Deriving it from the data makes that class of mismatch
 * impossible.
 */
export function monthRangeLabel(months: readonly string[]): string {
  if (months.length === 0) return "";
  const first = formatMonthKey(months[0]);
  const last = formatMonthKey(months[months.length - 1]);
  return first === last ? first : `${first} — ${last}`;
}
