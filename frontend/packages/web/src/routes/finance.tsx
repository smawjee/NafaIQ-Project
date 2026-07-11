import { createFileRoute } from "@tanstack/react-router";
import { Finance } from "@/features/finance/Finance";

export const Route = createFileRoute("/finance")({
  head: () => ({
    meta: [
      { title: "Finance — NafaIQ" },
      {
        name: "description",
        content: "Track income, expenses, budgets, bills and savings goals with AI guidance.",
      },
    ],
  }),
  component: Finance,
});
