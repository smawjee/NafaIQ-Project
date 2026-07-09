import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { WATCHLIST } from "@/lib/data";
import type { WatchlistState } from "./types";

const initialState: WatchlistState = {
  symbols: [...WATCHLIST],
};

const watchlistSlice = createSlice({
  name: "watchlist",
  initialState,
  reducers: {
    addWatchlistSymbol(state, action: PayloadAction<string>) {
      const sym = action.payload.toUpperCase().trim();
      if (sym && !state.symbols.includes(sym)) {
        state.symbols.push(sym);
      }
    },
    removeWatchlistSymbol(state, action: PayloadAction<string>) {
      const sym = action.payload.toUpperCase().trim();
      state.symbols = state.symbols.filter((s) => s !== sym);
    },
    resetWatchlist(state) {
      state.symbols = [...WATCHLIST];
    },
  },
});

export const { addWatchlistSymbol, removeWatchlistSymbol, resetWatchlist } = watchlistSlice.actions;
export default watchlistSlice.reducer;
