import { createFileRoute } from "@tanstack/react-router";
import { PSX } from "@/features/psx/PSX";

export const Route = createFileRoute("/psx")({
  head: () => ({
    meta: [
      { title: "PSX Market — NafaIQ Trading Terminal" },
      {
        name: "description",
        content:
          "Live KSE-100 candlestick terminal, top movers, sector heatmap and AI stock screener.",
      },
    ],
  }),
  component: PSX,
});
