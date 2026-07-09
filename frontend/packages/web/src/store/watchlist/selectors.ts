import type { RootState } from "../index";

export const selectWatchlistSymbols = (state: RootState) => state.watchlist.symbols;
