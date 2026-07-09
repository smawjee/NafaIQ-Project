import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { portfolioReducer } from "./portfolio";
import { financeReducer } from "./finance";
import { alertsReducer } from "./alerts";
import { watchlistReducer } from "./watchlist";
import { demoUserReducer } from "./demoUser";
import { persistMiddleware } from "./middleware";
import { loadPersistedState } from "./rehydrate";
import { resetDemoData } from "./reset";

const appReducer = combineReducers({
  portfolio: portfolioReducer,
  finance: financeReducer,
  alerts: alertsReducer,
  watchlist: watchlistReducer,
  demoUser: demoUserReducer,
});

// resetDemoData re-seeds every slice from its fixture initial state, so demo
// activity cannot leak across logout or into a real-user session.
const rootReducer: typeof appReducer = (state, action) =>
  appReducer(resetDemoData.match(action) ? undefined : state, action);

const preloaded = loadPersistedState<ReturnType<typeof appReducer>>() ?? undefined;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const store = configureStore<any, any, any>({
  reducer: rootReducer,
  preloadedState: preloaded,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({ thunk: true }).concat(persistMiddleware),
});

export { resetDemoData } from "./reset";

export type RootState = ReturnType<typeof appReducer>;
export type AppDispatch = typeof store.dispatch;
export type AppStore = typeof store;
