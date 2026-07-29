import { createFileRoute } from "@tanstack/react-router";
import { AdminAlerts } from "@/features/admin/pages/Alerts";

export const Route = createFileRoute("/admin/alerts")({
  component: AdminAlerts,
});
