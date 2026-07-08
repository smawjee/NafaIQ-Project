import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { portfolioReducer } from "./portfolio";
import { financeReducer } from "./finance";
import { alertsReducer } from "./alerts";
import { persistMiddleware } from "./middleware";
import { loadPersistedState } from "./rehydrate";

const rootReducer = combineReducers({
  portfolio: portfolioReducer,
  finance: financeReducer,
  alerts: alertsReducer,
});

const preloaded = loadPersistedState<ReturnType<typeof rootReducer>>() ?? undefined;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const store = configureStore<any, any, any>({
  reducer: rootReducer,
  preloadedState: preloaded,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({ thunk: true }).concat(persistMiddleware),
});

export type RootState = ReturnType<typeof rootReducer>;
export type AppDispatch = typeof store.dispatch;
export type AppStore = typeof store;
