import { useCallback, useEffect, useState } from "react";

const STORAGE_PREFIX = "nafaiq:psx:tf-map:v1";

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

/**
 * Per-symbol timeframe persistence (Phase 0 / B5).
 *
 * Switch stocks → each remembers its own selected timeframe. Backed by
 * localStorage so the choice survives page reloads. Falls back to a default
 * (6M) for symbols the user has never opened. SSR-safe.
 */
export function usePersistedTfMap(defaultTf: string = "6M"): {
  tfFor: (sym: string) => string;
  setTfFor: (sym: string, tf: string) => void;
} {
  const [map, setMap] = useState<Record<string, string>>(() => readMap(STORAGE_PREFIX));

  const setTfFor = useCallback((sym: string, tf: string) => {
    setMap((prev) => {
      if (prev[sym] === tf) return prev;
      return { ...prev, [sym]: tf };
    });
  }, []);

  // Write to localStorage in a side effect (not inside state updater)
  useEffect(() => {
    writeMap(STORAGE_PREFIX, map);
  }, [map]);

  const tfFor = useCallback((sym: string) => map[sym] ?? defaultTf, [map, defaultTf]);

  return { tfFor, setTfFor };
}
