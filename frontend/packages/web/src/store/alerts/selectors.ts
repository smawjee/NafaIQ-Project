import { createSelector } from "@reduxjs/toolkit";
import type { RootState } from "../index";

export const selectAlerts = (state: RootState) => state.alerts.alerts;
export const selectNotifications = (state: RootState) => state.alerts.notifications;

export const selectUnreadCount = createSelector(selectNotifications, (notifs) =>
  notifs.filter((n) => !n.read).length,
);
