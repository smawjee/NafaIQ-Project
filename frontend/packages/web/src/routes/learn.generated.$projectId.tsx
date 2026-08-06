import { createFileRoute } from "@tanstack/react-router";
import { GeneratedLessonPage } from "@/features/learn/studio/GeneratedLessonPage";

export const Route = createFileRoute("/learn/generated/$projectId")({
  head: () => ({ meta: [{ title: "Generated Lesson — NafaIQ Learn Hub" }] }),
  component: GeneratedLessonPage,
});
