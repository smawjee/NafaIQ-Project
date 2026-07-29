export const RANGES = ["1M", "3M", "6M", "1Y"] as const;

export const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

// Palette reused by both the sector and stock allocation donut charts.
export const ALLOCATION_PALETTE = [
  "#00d4aa",
  "#3b82f6",
  "#f59e0b",
  "#8b5cf6",
  "#6b7280",
  "#ec4899",
  "#10b981",
];

export const SHIELD_ACTIONS = [
  {
    title: "Add USD-hedged exposure",
    detail: "Shift 10% into export-heavy names (technology, textiles) that earn in USD.",
    points: 12,
  },
  {
    title: "Increase Oil & Gas weighting",
    detail: "Commodity-linked stocks track global prices and cushion rupee weakness.",
    points: 9,
  },
  {
    title: "Trim cash & PKR fixed income",
    detail: "Idle rupee holdings erode fastest during devaluation cycles.",
    points: 7,
  },
  {
    title: "Add gold / commodity proxy",
    detail: "A small allocation to gold-linked assets is a classic inflation hedge.",
    points: 6,
  },
];
