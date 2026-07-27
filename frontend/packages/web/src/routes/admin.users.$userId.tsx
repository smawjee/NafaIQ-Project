import { createFileRoute } from "@tanstack/react-router";
import { AdminUserDetail } from "@/features/admin/pages/UserDetail";

export const Route = createFileRoute("/admin/users/$userId")({
  component: AdminUserDetail,
});
