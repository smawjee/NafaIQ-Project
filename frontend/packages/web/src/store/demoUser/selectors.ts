import type { RootState } from "../index";

export const selectDemoSessionStartedAt = (state: RootState) => state.demoUser.sessionStartedAt;
