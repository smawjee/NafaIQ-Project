import { createFileRoute } from "@tanstack/react-router";
import { LearnHub } from "@/features/learn/hub/LearnHub";

export const Route = createFileRoute("/learn/")({
  head: () => ({
    meta: [
      { title: "Learn Hub — NafaIQ" },
      {
        name: "description",
        content:
          "Learn PSX investing from candlesticks to halal investing — lessons, videos, quizzes and an AI tutor, in plain Urdu and English.",
      },
    ],
  }),
  component: LearnHub,
});
