// Persisted finance store (alerts/notifs/transactions/bills/goals) with CRUD.
// Ported from web use-finance-store.ts; localStorage -> AsyncStorage (async
// hydrate). financeActions + selectors are otherwise verbatim.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";

import {
  ALERTS,
  type Alert,
  BILLS,
  type Bill,
  GOALS,
  type Goal,
  NOTIFS,
  type Notif,
  TRANSACTIONS,
  type Txn,
} from "@nafaiq/shared";

const KEY = "nafaiq:finance:v1";

export interface FinanceState {
  alerts: Alert[];
  notifications: Notif[];
  transactions: Txn[];
  bills: Bill[];
  goals: Goal[];
}

function seed(): FinanceState {
  return {
    alerts: ALERTS.map((a) => ({ ...a })),
    notifications: NOTIFS.map((n) => ({ ...n })),
    transactions: TRANSACTIONS.map((t) => ({ ...t })),
    bills: BILLS.map((b) => ({ ...b })),
    goals: GOALS.map((g) => ({ ...g })),
  };
}

let state: FinanceState = seed();
const listeners = new Set<() => void>();

// Hydrate from storage on load, then notify.
AsyncStorage.getItem(KEY)
  .then((raw) => {
    if (!raw) return;
    const parsed = JSON.parse(raw) as Partial<FinanceState>;
    const base = seed();
    state = {
      alerts: parsed.alerts ?? base.alerts,
      notifications: parsed.notifications ?? base.notifications,
      transactions: parsed.transactions ?? base.transactions,
      bills: parsed.bills ?? base.bills,
      goals: parsed.goals ?? base.goals,
    };
    listeners.forEach((l) => l());
  })
  .catch(() => {});

function persist() {
  AsyncStorage.setItem(KEY, JSON.stringify(state)).catch(() => {});
}

function setState(updater: (prev: FinanceState) => FinanceState) {
  state = updater(state);
  persist();
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function nowLabel() {
  return new Date().toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function dayLabel() {
  return new Date().toLocaleString("en-US", { month: "long", day: "numeric" });
}

export const financeActions = {
  addAlert(alert: Alert, notifMsg?: string) {
    setState((p) => ({
      ...p,
      alerts: [alert, ...p.alerts],
      notifications: notifMsg
        ? [{ time: nowLabel(), emoji: alert.emoji, msg: notifMsg, read: false }, ...p.notifications]
        : p.notifications,
    }));
  },
  toggleAlert(index: number) {
    setState((p) => ({ ...p, alerts: p.alerts.map((a, i) => (i === index ? { ...a, on: !a.on } : a)) }));
  },
  removeAlert(index: number) {
    setState((p) => ({ ...p, alerts: p.alerts.filter((_, i) => i !== index) }));
  },
  addTransaction(txn: Omit<Txn, "date"> & { date?: string }) {
    const full: Txn = { ...txn, date: txn.date || dayLabel() };
    setState((p) => ({ ...p, transactions: [full, ...p.transactions] }));
  },
  addBill(bill: Bill) {
    setState((p) => ({ ...p, bills: [...p.bills, bill] }));
  },
  markBillPaid(name: string) {
    setState((p) => {
      const bill = p.bills.find((b) => b.name === name);
      const txns = bill
        ? [
            { date: dayLabel(), merchant: bill.name, category: "Utilities", account: "HBL Current", amount: -bill.amount } as Txn,
            ...p.transactions,
          ]
        : p.transactions;
      return { ...p, bills: p.bills.filter((b) => b.name !== name), transactions: txns };
    });
  },
  addGoal(goal: Goal) {
    setState((p) => ({ ...p, goals: [...p.goals, goal] }));
  },
  contributeToGoal(name: string, amount: number) {
    setState((p) => ({
      ...p,
      goals: p.goals.map((g) => (g.name === name ? { ...g, saved: Math.min(g.saved + amount, g.target) } : g)),
      transactions: [
        { date: dayLabel(), merchant: `${name} Transfer`, category: "Savings", account: "Meezan Savings", amount: -amount } as Txn,
        ...p.transactions,
      ],
    }));
  },
};

export function useFinanceStore(): FinanceState {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => state,
  );
}
