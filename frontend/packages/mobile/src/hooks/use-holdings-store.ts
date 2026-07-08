// Persisted portfolio holdings store (add / update / remove). Shared so a
// holding added from the dashboard quick-add sheet shows up on the Portfolio
// screen. Same useSyncExternalStore + AsyncStorage pattern as the finance store.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";

import { HOLDINGS, type Holding } from "@nafaiq/shared";

const KEY = "nafaiq:holdings:v1";

function seed(): Holding[] {
  return HOLDINGS.map((h) => ({ ...h }));
}

let state: Holding[] = seed();
const listeners = new Set<() => void>();

AsyncStorage.getItem(KEY)
  .then((raw) => {
    if (!raw) return;
    const parsed = JSON.parse(raw) as Holding[];
    if (Array.isArray(parsed)) {
      state = parsed;
      listeners.forEach((l) => l());
    }
  })
  .catch(() => {});

function setState(next: Holding[]) {
  state = next;
  AsyncStorage.setItem(KEY, JSON.stringify(state)).catch(() => {});
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export const holdingsActions = {
  addHolding(h: Holding) {
    setState([...state, h]);
  },
  updateHolding(index: number, h: Holding) {
    setState(state.map((x, i) => (i === index ? h : x)));
  },
  removeHolding(index: number) {
    setState(state.filter((_, i) => i !== index));
  },
};

export function useHoldings(): Holding[] {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => state,
  );
}
