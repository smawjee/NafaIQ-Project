import { createFileRoute } from "@tanstack/react-router";
import { LessonPage } from "@/features/learn/lesson/LessonPage";

export const Route = createFileRoute("/learn/lesson/$id")({
  head: () => ({
    meta: [{ title: "Lesson — NafaIQ Learn Hub" }],
  }),
  component: LessonPage,
});
