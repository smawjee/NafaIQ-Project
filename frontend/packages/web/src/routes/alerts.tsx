import { createFileRoute } from "@tanstack/react-router";
import { Alerts } from "@/features/alerts/Alerts";

export const Route = createFileRoute("/alerts")({
  head: () => ({
    meta: [
      { title: "Alerts — NafaIQ" },
      {
        name: "description",
        content: "Manage stock price, bill, budget and goal alerts plus your notification history.",
      },
    ],
  }),
  component: Alerts,
});
