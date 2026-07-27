import { createFileRoute } from "@tanstack/react-router";
import { AdminOverview } from "@/features/admin/pages/Overview";

export const Route = createFileRoute("/admin/")({
  component: AdminOverview,
});
