import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ResultsView } from "./ResultsView";
import type { LessonContent } from "@/lib/learn/data";

vi.mock("@/hooks/use-lang", () => ({ useLang: () => ({ t: (value: string) => value }) }));
vi.mock("@/features/learn/lesson/lesson.utils", () => ({
  useCountUp: (_from: number, to: number) => to,
  buildShuffled: (questions: LessonContent["quiz"]) =>
    questions.map((q) => ({
      q,
      options: q.options.map((text, index) => ({ text, isCorrect: index === q.correct })),
    })),
}));

const lesson: LessonContent = {
  id: "generated-1",
  emoji: "📈",
  title: "Generated PSX lesson",
  subtitle: "Practice",
  category: "PSX Learning",
  accent: "#00d4aa",
  duration: "4 min",
  level: "Beginner",
  type: "article",
  presets: [],
  sections: [],
  quiz: [
    {
      q: "What is PSX?",
      options: ["Exchange", "Bank", "Fund", "Broker"],
      correct: 0,
      explanation: "It is an exchange.",
    },
  ],
};

describe("ResultsView practice mode", () => {
  it("keeps the native result UI but never claims XP", () => {
    render(
      <ResultsView
        lesson={lesson}
        correct={1}
        gain={0}
        startXp={100}
        practice
        nextId={null}
        onRetake={vi.fn()}
        onBackToLesson={vi.fn()}
        onContinue={vi.fn()}
      />,
    );
    expect(screen.getByText("Practice result saved")).toBeInTheDocument();
    expect(
      screen.getByText("Generated quizzes do not affect your XP or learning streak."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Added to your profile/)).not.toBeInTheDocument();
  });
});
