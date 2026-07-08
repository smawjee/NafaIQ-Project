/**
 * Single source of truth for number / currency / percent formatting.
 *
 * Rules (app-wide — do not re-implement per screen):
 *  - Digit grouping: Western 3-digit (1,234,567) via the "en-US" locale.
 *    We deliberately avoid "en-PK" because its grouping is inconsistent across
 *    runtimes (sometimes lakh "8,58,054", sometimes "858,054"), which caused
 *    Portfolio and Personal Finance to disagree.
 *  - Sign placement: always LEADING, e.g. "+2.27%", "-0.45%", "+PKR 2,500".
 */

import { localizeDigits } from "@/hooks/use-lang";

const GROUPING_LOCALE = "en-US";

/** Western 3-digit grouped number, e.g. 858054 -> "858,054" (Urdu numerals in UR mode). */
export function formatNumber(value: number, decimals = 0): string {
  return localizeDigits(
    value.toLocaleString(GROUPING_LOCALE, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }),
  );
}

/** Currency, e.g. 858054 -> "PKR 858,054". */
export function formatPKR(value: number, decimals = 0): string {
  return `PKR ${formatNumber(value, decimals)}`;
}

function leadingSign(value: number): string {
  return value > 0 ? "+" : value < 0 ? "-" : "";
}

/** Leading-sign number, e.g. 2500 -> "+2,500", -2500 -> "-2,500". */
export function formatSigned(value: number, decimals = 0): string {
  return `${leadingSign(value)}${formatNumber(Math.abs(value), decimals)}`;
}

/** Leading-sign percent, e.g. 2.27 -> "+2.27%", -0.45 -> "-0.45%". */
export function formatSignedPercent(value: number, decimals = 2): string {
  return `${leadingSign(value)}${formatNumber(Math.abs(value), decimals)}%`;
}

/** Leading-sign currency, e.g. 2500 -> "+PKR 2,500", -2500 -> "-PKR 2,500". */
export function formatSignedPKR(value: number, decimals = 0): string {
  return `${leadingSign(value)}PKR ${formatNumber(Math.abs(value), decimals)}`;
}
