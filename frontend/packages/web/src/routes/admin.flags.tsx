import { createFileRoute } from "@tanstack/react-router";
import { AdminFlags } from "@/features/admin/pages/Flags";

export const Route = createFileRoute("/admin/flags")({
  component: AdminFlags,
});
