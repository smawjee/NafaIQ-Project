import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RelatedLessons } from "../RelatedLessons";

const useRelatedLessons = vi.fn();

vi.mock("@/hooks/learn/use-learn-search", () => ({
  useRelatedLessons: (...args: unknown[]) => useRelatedLessons(...args),
}));

vi.mock("@/hooks/use-lang", () => ({
  useLang: () => ({ t: (value: string) => value }),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    params,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    params: { id: string };
  }) => (
    <a href={`/learn/lesson/${params.id}`} {...props}>
      {children}
    </a>
  ),
}));

describe("RelatedLessons", () => {
  beforeEach(() => {
    useRelatedLessons.mockReset();
  });

  it("renders each related lesson once when the API returns duplicate IDs", () => {
    useRelatedLessons.mockReturnValue([
      { lesson_id: "rsi", score: 0.9 },
      { lesson_id: "rsi", score: 0.8 },
      { lesson_id: "patterns", score: 0.7 },
    ]);

    render(<RelatedLessons lessonId="candlestick" />);

    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: /Understanding RSI/i })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: /5 Candle Patterns/i })).toHaveLength(1);
  });
});
