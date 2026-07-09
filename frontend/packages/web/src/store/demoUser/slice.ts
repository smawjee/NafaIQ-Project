import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { DemoUserState } from "./types";

const initialState: DemoUserState = {
  sessionStartedAt: null,
};

const demoUserSlice = createSlice({
  name: "demoUser",
  initialState,
  reducers: {
    demoSessionStarted(state, action: PayloadAction<string>) {
      if (!state.sessionStartedAt) {
        state.sessionStartedAt = action.payload;
      }
    },
  },
});

export const { demoSessionStarted } = demoUserSlice.actions;
export default demoUserSlice.reducer;
