import { useCallback, useEffect, useState } from "react";

/**
 * A boolean UI preference backed by localStorage, safe under SSR.
 *
 * The naive version of this — reading localStorage inside a `useState`
 * initialiser behind a `typeof window` check — is a hydration bug. The server
 * renders the fallback, the client's first render reads the stored value, the
 * two disagree, and React throws the tree away and re-renders it (error #418).
 * Production telemetry showed exactly that firing on the landing page; these
 * collapse/expand flags had the same defect for anyone who had ever toggled one.
 *
 * So: the first client render always matches the server (the fallback), and the
 * stored value is applied in an effect once hydration has committed. The cost is
 * one frame in the default state before a stored preference takes effect, which
 * is the standard trade and the same approach `use-landing-theme` takes with its
 * `hydrated` flag.
 *
 * For values that change outside React (language, cross-tab writes) prefer
 * `useSyncExternalStore` with a `getServerSnapshot`, as `use-lang` and
 * `use-persisted-tf-map` do. This hook is for simple per-component toggles.
 */
export function usePersistedBool(
  key: string,
  fallback = false,
): readonly [boolean, (next: boolean) => void] {
  const [value, setValue] = useState(fallback);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(key);
      if (stored !== null) setValue(stored === "1");
    } catch {
      // storage disabled / quota — keep the fallback, the toggle still works
    }
  }, [key]);

  const set = useCallback(
    (next: boolean) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, next ? "1" : "0");
      } catch {
        // ignore — in-memory state is still correct for this session
      }
    },
    [key],
  );

  return [value, set] as const;
}
