import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { ALERTS, NOTIFS } from "@/lib/finance/data";
import type { AlertState, Alert, Notif } from "./types";

function nowLabel() {
  const d = new Date();
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const initialState: AlertState = {
  alerts: ALERTS.map((a) => ({ ...a })),
  notifications: NOTIFS.map((n) => ({ ...n })),
};

const alertsSlice = createSlice({
  name: "alerts",
  initialState,
  reducers: {
    addAlert(state, action: PayloadAction<{ alert: Alert; notifMsg?: string }>) {
      const { alert, notifMsg } = action.payload;
      state.alerts.unshift(alert);
      if (notifMsg) {
        state.notifications.unshift({
          time: nowLabel(),
          emoji: alert.emoji,
          msg: notifMsg,
          read: false,
        });
      }
    },
    toggleAlert(state, action: PayloadAction<number>) {
      const alert = state.alerts[action.payload];
      if (alert) {
        alert.on = !alert.on;
      }
    },
    removeAlert(state, action: PayloadAction<number>) {
      state.alerts.splice(action.payload, 1);
    },
    markNotifRead(state, action: PayloadAction<number>) {
      const notif = state.notifications[action.payload];
      if (notif) {
        notif.read = true;
      }
    },
    clearAllNotifs(state) {
      state.notifications = [];
    },
    resetAlerts(state) {
      state.alerts = ALERTS.map((a) => ({ ...a }));
      state.notifications = NOTIFS.map((n) => ({ ...n }));
    },
  },
});

export const { addAlert, toggleAlert, removeAlert, markNotifRead, clearAllNotifs, resetAlerts } =
  alertsSlice.actions;
export default alertsSlice.reducer;
