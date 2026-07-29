import { createFileRoute } from "@tanstack/react-router";
import { MutualFundsTab } from "@/features/funds/MutualFundsTab";

export const Route = createFileRoute("/funds")({
  head: () => ({
    meta: [
      { title: "Mutual Funds — NafaIQ" },
      { name: "description", content: "Browse mutual funds NAV history and performance." },
    ],
  }),
  component: MutualFundsTab,
});
