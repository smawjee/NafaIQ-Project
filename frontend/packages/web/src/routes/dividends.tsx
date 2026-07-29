import { createFileRoute } from "@tanstack/react-router";
import { DividendCalendar } from "@/features/dividends/DividendCalendar";

export const Route = createFileRoute("/dividends")({
  head: () => ({
    meta: [
      { title: "Dividends — NafaIQ" },
      { name: "description", content: "PSX dividend announcements and calendar." },
    ],
  }),
  component: DividendCalendar,
});
