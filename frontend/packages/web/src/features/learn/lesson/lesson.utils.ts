import { useEffect, useState } from "react";
import { type QuizQuestion } from "@/lib/learn/data";

export function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export interface ShuffledQ {
  q: QuizQuestion;
  options: { text: string; isCorrect: boolean }[];
}

export function buildShuffled(quiz: QuizQuestion[]): ShuffledQ[] {
  return quiz.map((q) => ({
    q,
    options: shuffle(q.options.map((text, i) => ({ text, isCorrect: i === q.correct }))),
  }));
}

export function useCountUp(from: number, to: number, ms = 1000) {
  const [val, setVal] = useState(from);
  useEffect(() => {
    if (from === to) {
      setVal(to);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / ms);
      setVal(Math.round(from + (to - from) * p));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [from, to, ms]);
  return val;
}
