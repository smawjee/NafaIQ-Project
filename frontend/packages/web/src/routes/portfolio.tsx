import { createFileRoute } from "@tanstack/react-router";
import { Portfolio } from "@/features/portfolio/Portfolio";

export const Route = createFileRoute("/portfolio")({
  head: () => ({
    meta: [
      { title: "Portfolio — NafaIQ" },
      {
        name: "description",
        content: "Track holdings, performance vs KSE-100, allocation and AI portfolio reports.",
      },
    ],
  }),
  component: Portfolio,
});
