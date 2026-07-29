import { useCallback, useSyncExternalStore } from "react";

const STORAGE_PREFIX = "nafaiq:psx:tf-map:v1";

/** Server snapshot — a stable reference, so useSyncExternalStore doesn't loop. */
const EMPTY_MAP: Record<string, string> = {};

function readMap(key: string): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function writeMap(key: string, value: Record<string, string>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore quota / disabled storage — the in-memory map still works
  }
}

// Module-level store, mirroring hooks/use-lang.ts. The map is one localStorage
// key, so every caller must observe the same value — per-hook state would let
// two mounted components drift apart and race each other's writes.
let current: Record<string, string> = readMap(STORAGE_PREFIX);
const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/**
 * Per-symbol timeframe persistence (Phase 0 / B5).
 *
 * Switch stocks → each remembers its own selected timeframe. Backed by
 * localStorage so the choice survives page reloads. Falls back to a default
 * (6M) for symbols the user has never opened.
 *
 * SSR-safe: reading localStorage during render would make the server ({}) and
 * client (stored map) disagree and blow up hydration. useSyncExternalStore
 * hydrates from getServerSnapshot, then re-renders from the real store — so
 * writes only ever happen in setTfFor, never from an effect that could fire
 * with an empty map and clobber what's on disk.
 */
export function usePersistedTfMap(defaultTf: string = "6M"): {
  tfFor: (sym: string) => string;
  setTfFor: (sym: string, tf: string) => void;
} {
  const map = useSyncExternalStore(
    subscribe,
    () => current,
    () => EMPTY_MAP,
  );

  const setTfFor = useCallback((sym: string, tf: string) => {
    if (current[sym] === tf) return;
    current = { ...current, [sym]: tf };
    writeMap(STORAGE_PREFIX, current);
    listeners.forEach((l) => l());
  }, []);

  const tfFor = useCallback((sym: string) => map[sym] ?? defaultTf, [map, defaultTf]);

  return { tfFor, setTfFor };
}
