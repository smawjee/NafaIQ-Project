/**
 * Redux store: slice reducers plus the cross-slice `resetDemoData` invariant.
 *
 * `resetDemoData` is the mechanism that stops one account's local playground
 * data reaching another — src/hooks/use-auth.tsx dispatches it on logout and
 * whenever a real (non-demo) account becomes active. It had no test.
 */
import { describe, expect, it } from "vitest";
import { configureStore } from "@reduxjs/toolkit";

import { rootReducer, resetDemoData } from "@/store";
import { addWatchlistSymbol, removeWatchlistSymbol, resetWatchlist } from "@/store/watchlist";
import { demoSessionStarted } from "@/store/demoUser";
import { WATCHLIST } from "@/lib/data";

function makeStore() {
  return configureStore({
    reducer: rootReducer,
    middleware: (getDefault) => getDefault({ serializableCheck: false }),
  });
}

describe("watchlist slice", () => {
  it("seeds from the shipped default watchlist", () => {
    expect(makeStore().getState().watchlist.symbols).toEqual([...WATCHLIST]);
  });

  it("appends a new symbol, upper-cased and trimmed", () => {
    const store = makeStore();
    store.dispatch(addWatchlistSymbol("  mebl "));
    expect(store.getState().watchlist.symbols).toContain("MEBL");
  });

  it("is idempotent — adding an existing symbol does not duplicate it", () => {
    const store = makeStore();
    const existing = store.getState().watchlist.symbols[0];
    const before = store.getState().watchlist.symbols.length;

    store.dispatch(addWatchlistSymbol(existing.toLowerCase()));

    expect(store.getState().watchlist.symbols.length).toBe(before);
  });

  it("ignores an empty or whitespace-only symbol", () => {
    const store = makeStore();
    const before = store.getState().watchlist.symbols.length;

    store.dispatch(addWatchlistSymbol("   "));
    store.dispatch(addWatchlistSymbol(""));

    expect(store.getState().watchlist.symbols.length).toBe(before);
  });

  it("removes case-insensitively", () => {
    const store = makeStore();
    store.dispatch(addWatchlistSymbol("MEBL"));
    store.dispatch(removeWatchlistSymbol("mebl"));
    expect(store.getState().watchlist.symbols).not.toContain("MEBL");
  });

  it("removing an absent symbol is a no-op", () => {
    const store = makeStore();
    const before = [...store.getState().watchlist.symbols];
    store.dispatch(removeWatchlistSymbol("NOTREAL"));
    expect(store.getState().watchlist.symbols).toEqual(before);
  });

  it("resetWatchlist restores the shipped defaults", () => {
    const store = makeStore();
    store.dispatch(addWatchlistSymbol("MEBL"));
    store.dispatch(removeWatchlistSymbol(WATCHLIST[0]));

    store.dispatch(resetWatchlist());

    expect(store.getState().watchlist.symbols).toEqual([...WATCHLIST]);
  });
});

describe("demoUser slice", () => {
  it("records the first demo session start", () => {
    const store = makeStore();
    store.dispatch(demoSessionStarted("2026-07-28T09:00:00.000Z"));
    expect(store.getState().demoUser.sessionStartedAt).toBe("2026-07-28T09:00:00.000Z");
  });

  it("keeps the ORIGINAL start time when dispatched again", () => {
    // use-auth.tsx fires this on every auth-state change while the demo user is
    // signed in; the elapsed-session display would reset on each one if this
    // guard were dropped.
    const store = makeStore();
    store.dispatch(demoSessionStarted("2026-07-28T09:00:00.000Z"));
    store.dispatch(demoSessionStarted("2026-07-28T11:30:00.000Z"));
    expect(store.getState().demoUser.sessionStartedAt).toBe("2026-07-28T09:00:00.000Z");
  });
});

describe("resetDemoData", () => {
  it("re-seeds every slice back to its initial state", () => {
    const store = makeStore();
    const pristine = makeStore().getState();

    store.dispatch(addWatchlistSymbol("MEBL"));
    store.dispatch(demoSessionStarted("2026-07-28T09:00:00.000Z"));
    expect(store.getState()).not.toEqual(pristine);

    store.dispatch(resetDemoData());

    expect(store.getState()).toEqual(pristine);
  });

  it("clears the demo session marker specifically", () => {
    const store = makeStore();
    store.dispatch(demoSessionStarted("2026-07-28T09:00:00.000Z"));

    store.dispatch(resetDemoData());

    expect(store.getState().demoUser.sessionStartedAt).toBeNull();
  });

  it("leaves no trace of a removed default symbol after reset", () => {
    // The leakage shape that matters: user A deletes a default holding/symbol,
    // logs out, user B signs in and must not inherit the deletion.
    const store = makeStore();
    store.dispatch(removeWatchlistSymbol(WATCHLIST[0]));
    expect(store.getState().watchlist.symbols).not.toContain(WATCHLIST[0]);

    store.dispatch(resetDemoData());

    expect(store.getState().watchlist.symbols).toEqual([...WATCHLIST]);
  });

  it("covers all five slices", () => {
    expect(Object.keys(makeStore().getState()).sort()).toEqual([
      "alerts",
      "demoUser",
      "finance",
      "portfolio",
      "watchlist",
    ]);
  });
});
