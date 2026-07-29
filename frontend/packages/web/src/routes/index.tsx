import { createFileRoute } from "@tanstack/react-router";
import { Landing } from "@/features/landing/Landing";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "NafaIQ — PSX, Finance & AI in One Terminal" },
      {
        name: "description",
        content:
          "Track markets, manage money, and get AI insights — built around Pakistan's financial reality. Install free as a web app on iOS, Android & desktop.",
      },
      { property: "og:title", content: "NafaIQ — PSX, Finance & AI in One Terminal" },
      {
        property: "og:description",
        content:
          "Track markets, manage money, and get AI insights — built around Pakistan's financial reality.",
      },
    ],
  }),
  component: Landing,
});
