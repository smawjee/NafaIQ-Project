import { createFileRoute } from "@tanstack/react-router";
import { Dashboard } from "@/features/dashboard/Dashboard";

export const Route = createFileRoute("/app")({
  head: () => ({
    meta: [
      { title: "Dashboard — NafaIQ" },
      {
        name: "description",
        content: "Your net worth, portfolio, spending and PSX signals at a glance.",
      },
    ],
  }),
  component: Dashboard,
});
