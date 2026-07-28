/**
 * URL-backed state for admin list screens.
 *
 * An operations console is used collaboratively: "look at these suspended Pro
 * accounts" should be a link, a refresh shouldn't dump you back to page 1, and
 * browser back should undo a filter. That only works if the filter/sort/page
 * state lives in the route's search params rather than in component state.
 *
 * The coercers below exist because search params are attacker-controlled text.
 * `validateSearch` runs on every navigation, so it must never throw and never
 * hand a page something it can't render — every value is clamped to a known-good
 * range, falling back to the default rather than rejecting the navigation.
 */
import { useCallback } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";

/** Trimmed string, length-capped. Anything non-string becomes "". */
export function coerceStr(value: unknown, maxLength = 200): string {
  return typeof value === "string" ? value.slice(0, maxLength) : "";
}

/** Positive integer, clamped. Rejects NaN/Infinity/floats/negatives. */
export function coerceInt(value: unknown, fallback: number, min = 1, max = 1_000_000): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.floor(n)));
}

/** One of `allowed`, else the fallback. */
export function coerceEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

/** Optional enum — "" means "no filter applied". */
export function coerceOptionalEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
): T | "" {
  return typeof value === "string" && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : "";
}

/**
 * Read + patch the current route's search params.
 *
 * `replace` distinguishes the two kinds of change:
 *   - `true`  for keystroke-level edits (the debounced search box) — otherwise
 *             typing one word buries the previous view under a dozen history
 *             entries and Back becomes useless.
 *   - `false` for deliberate steps (page, sort, a filter selection) so Back
 *             actually undoes the thing the admin just did.
 */
export function useTableSearch<T extends object>(from: string) {
  // The route id is a runtime string here, so the router's per-route generic
  // inference can't apply — the options object is cast once and the caller's
  // `T` (exported alongside each route's validateSearch) restores type safety.
  const search = useSearch({ from } as never) as T;
  const navigate = useNavigate({ from } as never);

  const setSearch = useCallback(
    (patch: Partial<T>, opts?: { replace?: boolean }) => {
      void navigate({
        search: ((prev: T) => ({ ...prev, ...patch })) as never,
        replace: opts?.replace ?? false,
      });
    },
    [navigate],
  );

  /**
   * Patch filters and return to page 1 in the SAME navigation.
   *
   * Doing it as two calls would briefly request page N of a narrower result set
   * — a wasted round-trip that can render an empty "no results" flash.
   */
  const setFilter = useCallback(
    (patch: Partial<T>, opts?: { replace?: boolean }) => {
      setSearch({ ...patch, page: 1 } as Partial<T>, opts);
    },
    [setSearch],
  );

  return { search, setSearch, setFilter };
}
