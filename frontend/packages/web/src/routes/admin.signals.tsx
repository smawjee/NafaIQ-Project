import { createFileRoute } from "@tanstack/react-router";
import { AdminSignals } from "@/features/admin/pages/Monitoring";

export const Route = createFileRoute("/admin/signals")({
  component: AdminSignals,
});
