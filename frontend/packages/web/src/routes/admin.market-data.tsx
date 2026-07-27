import { createFileRoute } from "@tanstack/react-router";
import { AdminMarketData } from "@/features/admin/pages/Monitoring";

export const Route = createFileRoute("/admin/market-data")({
  component: AdminMarketData,
});
