import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { HOLDINGS } from "@/lib/data";
import type { PortfolioState, Holding } from "./types";

const initialState: PortfolioState = {
  holdings: HOLDINGS.map((h) => ({ ...h })),
};

const portfolioSlice = createSlice({
  name: "portfolio",
  initialState,
  reducers: {
    addHolding(state, action: PayloadAction<Holding>) {
      state.holdings.push(action.payload);
    },
    updateHolding(state, action: PayloadAction<{ index: number; holding: Holding }>) {
      const { index, holding } = action.payload;
      if (index >= 0 && index < state.holdings.length) {
        state.holdings[index] = holding;
      }
    },
    removeHolding(state, action: PayloadAction<number>) {
      state.holdings.splice(action.payload, 1);
    },
    resetHoldings(state) {
      state.holdings = HOLDINGS.map((h) => ({ ...h }));
    },
  },
});

export const { addHolding, updateHolding, removeHolding, resetHoldings } = portfolioSlice.actions;
export default portfolioSlice.reducer;
