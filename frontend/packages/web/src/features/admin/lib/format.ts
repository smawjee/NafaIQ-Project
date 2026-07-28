/**
 * Formatting helpers shared across the admin console.
 *
 * Every timestamp in the console is rendered in Asia/Karachi (PKT) — the
 * platform's canonical zone — so an admin in any timezone reads the same clock
 * the scheduler and audit log write in.
 */

export const PKT = "Asia/Karachi";

/** Absolute PKT timestamp. Returns an em dash for null/invalid input. */
export function formatPkt(value: string | null | undefined, withTime = true): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-GB", {
    timeZone: PKT,
    year: "numeric",
    month: "short",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

/**
 * Coarse relative age ("3m ago", "2d ago"). Used as the primary label on dense
 * tables where an absolute timestamp costs too much horizontal space; the
 * absolute value is always still available in the cell's `title` tooltip.
 */
export function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const secs = Math.round((Date.now() - d.getTime()) / 1000);
  if (secs < 0) return "in the future";
  if (secs < 45) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.round(months / 12)}y ago`;
}

/** Thousands-separated integer. Non-numbers render as an em dash, never "NaN". */
export function formatNumber(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toLocaleString("en-US");
}

/** Compact magnitude for KPI tiles (12.4K, 3.1M). */
export function formatCompact(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  if (Math.abs(value) < 1000) return value.toLocaleString("en-US");
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(
    value,
  );
}

export function formatPercent(value: unknown, digits = 1): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

/** "admin.user.tier" -> "User tier" — audit actions as readable prose. */
export function humanizeAction(action: string): string {
  const trimmed = action.replace(/^admin\./, "").replace(/[._]/g, " ");
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
}

/** "new_users_7d" -> "New users 7d" — for dynamically-keyed metric blocks. */
export function humanizeKey(key: string): string {
  const s = key.replace(/[._]/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Initials for an avatar chip. Falls back to "?" so it never renders empty. */
export function initials(value: string | null | undefined): string {
  if (!value) return "?";
  const name = value.split("@")[0] ?? value;
  const parts = name.split(/[.\s_-]+/).filter(Boolean);
  if (parts.length === 0) return value.slice(0, 1).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

/**
 * Serialize rows to an RFC 4180 CSV document.
 *
 * Kept separate from the download so the escaping rules — the part with real
 * consequences — can be tested without a DOM.
 *
 * Two hardening rules:
 *  - Every value is quoted and internal quotes are doubled.
 *  - A leading =, +, - or @ is prefixed with an apostrophe so a spreadsheet
 *    treats exported data as text instead of executing it as a formula. Admin
 *    exports contain user-supplied display names, which is exactly the vector
 *    CSV injection uses.
 *
 * The leading BOM makes Excel read the file as UTF-8; without it Urdu display
 * names arrive mangled.
 */
export function toCsv(columns: string[], rows: unknown[][]): string {
  const escape = (v: unknown): string => {
    if (v == null) return "";
    let s = typeof v === "object" ? JSON.stringify(v) : String(v);
    if (/^[=+\-@]/.test(s)) s = `'${s}`;
    return `"${s.replace(/"/g, '""')}"`;
  };
  const body = [columns.map(escape).join(","), ...rows.map((r) => r.map(escape).join(","))].join(
    "\r\n",
  );
  return "﻿" + body;
}

/** Serialize rows to CSV and trigger a browser download. */
export function downloadCsv(filename: string, columns: string[], rows: unknown[][]): void {
  const blob = new Blob([toCsv(columns, rows)], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
