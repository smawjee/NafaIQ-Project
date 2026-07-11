import { createFileRoute } from "@tanstack/react-router";
import { StockDetail } from "@/features/stock/StockDetail";

export const Route = createFileRoute("/stock/$ticker")({
  head: ({ params }) => ({
    meta: [
      { title: `${params.ticker} — NafaIQ` },
      {
        name: "description",
        content: `${params.ticker} price chart, AI technical analysis and signal breakdown on NafaIQ.`,
      },
    ],
  }),
  component: StockDetail,
});
