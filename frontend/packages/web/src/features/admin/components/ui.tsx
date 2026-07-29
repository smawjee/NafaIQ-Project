/**
 * Barrel for the admin component library.
 *
 * Pages import everything from here so the underlying file layout can change
 * without touching 11 screens. New primitives belong in `primitives.tsx`,
 * `states.tsx`, `DataTable.tsx` etc. — not in this file.
 */
export * from "./primitives";
export * from "./states";
export * from "./DataTable";
export * from "./PageHeader";
export * from "./filters";
export { Drawer } from "./Drawer";
export * from "./charts";

export {
  formatPkt,
  formatNumber,
  formatCompact,
  formatPercent,
  relativeTime,
  humanizeAction,
  humanizeKey,
  initials,
  downloadCsv,
} from "@/features/admin/lib/format";
