import { createAction } from "@reduxjs/toolkit";

// Global reset for all demo/local slices. Dispatched on logout, when a real
// (non-demo) account becomes active, and by the "Reset Demo Data" control.
// Kept in its own module so the persist middleware can react to it without
// importing the store (which would be a circular import).
export const RESET_DEMO_DATA = "demo/resetAll";

export const resetDemoData = createAction(RESET_DEMO_DATA);
