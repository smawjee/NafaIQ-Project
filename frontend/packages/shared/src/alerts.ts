/**
 * Price-alert conditions — the ONE definition both apps use.
 *
 * Mirrors `PriceCondition` in `backend/src/app/schemas/alerts.py`, which is
 * itself enforced twice more: a pydantic Literal on the API and a CHECK
 * constraint on `price_alerts.condition` (migration 20260730090000).
 *
 * This lives in @nafaiq/shared rather than in the web app because it was
 * previously spelled out in EIGHT places across web and mobile — every alert
 * entry point had its own hardcoded `["above","below"]` pair, so adding a
 * condition to the backend left most of the product unable to express it. The
 * cost of that drift was not theoretical: the web alerts screen offered 2 of 9
 * conditions over 4 of ~1,077 symbols, and the mobile assistant's draft
 * confirmation card offered 2, while the API and the DB happily accepted all 9.
 */

export type PriceCondition =
  | "above"
  | "below"
  | "cross_above"
  | "cross_below"
  | "pct_change_above"
  | "pct_change_below"
  | "volume_spike"
  | "high_52w"
  | "low_52w";

export interface PriceConditionSpec {
  value: PriceCondition;
  /** Shown in a picker. */
  label: string;
  /** Unit beside the threshold input. Empty string => there is no threshold. */
  unit: string;
  /** Placeholder for the threshold input. */
  placeholder: string;
  /** One-line explanation so the option is self-explanatory without docs. */
  hint: string;
}

/**
 * Order is deliberate: the price-level conditions people reach for most come
 * first, the exotic ones last.
 */
export const PRICE_CONDITIONS: PriceConditionSpec[] = [
  {
    value: "above",
    label: "Price rises above",
    unit: "PKR",
    placeholder: "302",
    hint: "Fires whenever the price is at or above your threshold.",
  },
  {
    value: "below",
    label: "Price falls below",
    unit: "PKR",
    placeholder: "280",
    hint: "Fires whenever the price is at or below your threshold.",
  },
  {
    value: "cross_above",
    label: "Price crosses above",
    unit: "PKR",
    placeholder: "302",
    hint: "Only on the crossing — not if it was already above.",
  },
  {
    value: "cross_below",
    label: "Price crosses below",
    unit: "PKR",
    placeholder: "280",
    hint: "Only on the crossing — not if it was already below.",
  },
  {
    value: "pct_change_above",
    label: "Rises by at least",
    unit: "%",
    placeholder: "5",
    hint: "Based on today's move. A fall will not trigger this.",
  },
  {
    value: "pct_change_below",
    label: "Falls by at least",
    unit: "%",
    placeholder: "5",
    hint: "Based on today's move. A rise will not trigger this.",
  },
  {
    value: "volume_spike",
    label: "Volume spikes to",
    unit: "×",
    placeholder: "3",
    hint: "Multiple of the symbol's 1-year average daily volume.",
  },
  {
    value: "high_52w",
    label: "Hits a 52-week high",
    unit: "",
    placeholder: "",
    hint: "No threshold needed — the high itself is the trigger.",
  },
  {
    value: "low_52w",
    label: "Hits a 52-week low",
    unit: "",
    placeholder: "",
    hint: "No threshold needed — the low itself is the trigger.",
  },
];

/** Conditions with no threshold; hide the input and send 0. */
export const THRESHOLDLESS_CONDITIONS: ReadonlySet<PriceCondition> =
  new Set<PriceCondition>(["high_52w", "low_52w"]);

export function conditionSpec(value: PriceCondition | string): PriceConditionSpec {
  return (
    PRICE_CONDITIONS.find((c) => c.value === value) ?? PRICE_CONDITIONS[0]
  );
}

/**
 * Human label for an alert, e.g. "HBL rises above PKR 302" / "HBL volume spikes
 * to 3×" / "HBL hits a 52-week high".
 *
 * Every list that shows a saved alert must go through this. The lists used to
 * interpolate `${symbol} ${condition} PKR ${price}` directly, which rendered a
 * volume alert as "HBL volume_spike PKR 3" — the raw enum with the wrong unit.
 * A create form that succeeds and a list that then misreports what you armed is
 * worse than not having the feature.
 */
export function describeCondition(
  symbol: string,
  condition: PriceCondition | string,
  threshold: number | string | null | undefined,
): string {
  const spec = conditionSpec(condition);
  const label = spec.label.toLowerCase();
  if (THRESHOLDLESS_CONDITIONS.has(spec.value)) return `${symbol} ${label}`;

  const n = typeof threshold === "number" ? threshold : Number(threshold ?? 0);
  const amount = Number.isFinite(n) ? n : 0;
  // PKR leads the number ("PKR 302"); % and × trail it ("5%", "3×").
  const value = spec.unit === "PKR" ? `PKR ${amount}` : `${amount}${spec.unit}`;
  return `${symbol} ${label} ${value}`;
}
