import { createFileRoute } from "@tanstack/react-router";
import { AdminRoles } from "@/features/admin/pages/Roles";

export const Route = createFileRoute("/admin/roles")({
  component: AdminRoles,
});
