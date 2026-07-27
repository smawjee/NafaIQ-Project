import { createFileRoute } from "@tanstack/react-router";
import { AdminSystem } from "@/features/admin/pages/Monitoring";

export const Route = createFileRoute("/admin/system")({
  component: AdminSystem,
});
