// Guards the known duplication between web's lesson data and @nafaiq/shared's:
// web/src/lib/learn/data.ts carries its own copy of LESSON_CONTENT, and the
// learn-corpus export (frontend/packages/shared/scripts/export-learn-corpus.ts)
// reads the SHARED copy. If the two drift, the corpus silently diverges from
// what the web app shows. This test extracts every user-facing string from both
// copies by walking the imported data structures (not by parsing source text)
// and asserts per-lesson equality.
//
// NOTE: web has no `@nafaiq/shared` workspace dependency (nothing in web/src
// imports it, and it is absent from web/package.json), so the shared module is
// imported via a relative path instead of the package alias. If web ever gains
// the workspace dep, switch this to `import ... from "@nafaiq/shared"`.
import { describe, expect, it } from "vitest";

import { LESSON_CONTENT as WEB_LESSON_CONTENT } from "../data";
import { LESSON_CONTENT as SHARED_LESSON_CONTENT } from "../../../../../shared/src/lesson-content";

interface LessonLike {
  title: string;
  sections: {
    id: string;
    heading: string;
    blocks: (
      | { type: "p"; text: string }
      | { type: "callout"; kind: string; text: string }
      | { type: "formula"; lines: string[] }
      | { type: "table"; head: string[]; rows: string[][] }
    )[];
  }[];
  quiz: { q: string; options: string[]; correct: number; explanation: string }[];
}

/** Flatten every user-facing string literal in a lesson into a sorted multiset. */
function extractStrings(lesson: LessonLike): string[] {
  const out: string[] = [lesson.title];
  for (const section of lesson.sections) {
    // section.id, not just the heading: ids are what the RAG index stores and
    // what deep links (/learn/lesson/$id#sectionId) and related-lessons resolve
    // against. A drift in ids between the two copies breaks navigation while
    // every visible string still matches — the exact failure this test existed
    // to catch and didn't.
    out.push(`#${section.id}`);
    out.push(section.heading);
    for (const block of section.blocks) {
      switch (block.type) {
        case "p":
        case "callout":
          out.push(block.text);
          break;
        case "formula":
          out.push(...block.lines);
          break;
        case "table":
          out.push(...block.head);
          for (const row of block.rows) out.push(...row);
          break;
      }
    }
  }
  for (const question of lesson.quiz) {
    out.push(question.q, ...question.options, question.explanation);
  }
  return out.sort();
}

describe("web LESSON_CONTENT stays aligned with @nafaiq/shared LESSON_CONTENT", () => {
  const webIds = Object.keys(WEB_LESSON_CONTENT).sort();
  const sharedIds = Object.keys(SHARED_LESSON_CONTENT).sort();

  it("exposes the same lesson ids", () => {
    expect(webIds).toEqual(sharedIds);
    expect(webIds.length).toBeGreaterThanOrEqual(10);
  });

  it.each(sharedIds)("lesson '%s' has identical strings in both copies", (id) => {
    const webLesson = WEB_LESSON_CONTENT[id] as LessonLike;
    const sharedLesson = SHARED_LESSON_CONTENT[id] as LessonLike;
    expect(webLesson).toBeDefined();
    expect(extractStrings(webLesson)).toEqual(extractStrings(sharedLesson));
  });
});
