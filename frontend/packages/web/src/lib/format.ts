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

/** Compact magnitude, e.g. 2.4e12 -> "2.4T", 2.15e11 -> "215B", 4.5e7 -> "45M". */
export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const units: [number, string][] = [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  for (const [threshold, suffix] of units) {
    if (abs >= threshold) {
      const scaled = abs / threshold;
      // One decimal below 100 (2.4T, 45.6B), none above (215B, 312K).
      const digits = scaled < 100 ? 1 : 0;
      return `${sign}${localizeDigits(scaled.toFixed(digits))}${suffix}`;
    }
  }
  return `${sign}${formatNumber(abs, 0)}`;
}

/** Compact currency, e.g. 2.15e11 -> "PKR 215B". */
export function formatCompactPKR(value: number): string {
  return `PKR ${formatCompact(value)}`;
}
