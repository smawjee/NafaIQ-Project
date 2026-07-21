import { createFileRoute } from "@tanstack/react-router";
import { MonetaryTool } from "@/features/monetary/MonetaryTool";

export const Route = createFileRoute("/monetary")({
  head: () => ({
    meta: [
      { title: "Monetary Desk - NafaIQ" },
      {
        name: "description",
        content: "Live USD to PKR conversion, popular currency rates, and Pakistan gold and silver reference prices with source checks.",
      },
    ],
  }),
  component: MonetaryTool,
});
