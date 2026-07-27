import { createFileRoute } from "@tanstack/react-router";
import { AdminAiOps } from "@/features/admin/pages/Monitoring";

export const Route = createFileRoute("/admin/ai")({
  component: AdminAiOps,
});
