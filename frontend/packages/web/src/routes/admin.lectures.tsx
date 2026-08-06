import { createFileRoute } from "@tanstack/react-router";
import { AdminLectures } from "@/features/admin/pages/Lectures";

export const Route = createFileRoute("/admin/lectures")({
  component: AdminLectures,
});
