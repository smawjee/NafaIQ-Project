import type { Alert, Notif } from "@/lib/finance/data";

export type { Alert, Notif };

export interface AlertState {
  alerts: Alert[];
  notifications: Notif[];
}
