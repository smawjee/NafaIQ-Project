import { createFileRoute } from "@tanstack/react-router";
import { AdminAudit } from "@/features/admin/pages/Audit";

export const Route = createFileRoute("/admin/audit")({
  component: AdminAudit,
});
