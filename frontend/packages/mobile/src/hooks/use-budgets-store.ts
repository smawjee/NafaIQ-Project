// Per-month budgets store. The current month is seeded from BUDGETS; every other
// month starts empty (so future months show no budget until the user adds one).
// Keyed by "MMM YYYY" (e.g. "Oct 2026"). AsyncStorage-backed.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";

import { BUDGETS, type Budget } from "@nafaiq/shared";

const KEY = "nafaiq:budgets:v1";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Build the "MMM YYYY" key for a month `offset` from the current month. */
export function monthKeyFor(offset: number): string {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

type BudgetMap = Record<string, Budget[]>;

function seed(): BudgetMap {
  return { [monthKeyFor(0)]: BUDGETS.map((b) => ({ ...b })) };
}

let state: BudgetMap = seed();
const listeners = new Set<() => void>();

AsyncStorage.getItem(KEY)
  .then((raw) => {
    if (!raw) return;
    const parsed = JSON.parse(raw) as BudgetMap;
    // Keep the current-month seed available even after a month rollover.
    state = { ...seed(), ...parsed };
    listeners.forEach((l) => l());
  })
  .catch(() => {});

function setState(next: BudgetMap) {
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

export const budgetsActions = {
  addBudget(month: string, budget: Budget) {
    setState({ ...state, [month]: [...(state[month] ?? []), budget] });
  },
};

export function useBudgets(): BudgetMap {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => state,
  );
}
