import { createFileRoute } from "@tanstack/react-router";
import { AdminSubscriptions } from "@/features/admin/pages/Subscriptions";

export const Route = createFileRoute("/admin/subscriptions")({
  component: AdminSubscriptions,
});
