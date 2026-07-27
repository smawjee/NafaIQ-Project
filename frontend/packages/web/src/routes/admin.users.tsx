import { createFileRoute } from "@tanstack/react-router";
import { AdminUsers } from "@/features/admin/pages/Users";

export const Route = createFileRoute("/admin/users")({
  component: AdminUsers,
});
