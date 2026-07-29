// Export the Learn Hub content as a retrieval corpus for the backend ingester.
//
// Usage:  pnpm --filter @nafaiq/shared run export:learn-corpus
// Output: backend/data/learn_corpus.json  (generated artifact — gitignored)
//
// The output is DETERMINISTIC: the same inputs always produce byte-identical
// output (chunks sorted by source_id via codepoint compare, no timestamps, no
// randomness), so the ingester can diff/re-run safely.
//
// FROZEN OUTPUT CONTRACT (the backend ingester is built against exactly this):
//   { "version": 1, "chunks": [{ source_type, source_id, lesson_id, section_id,
//     title, heading, text_en, text_ur, metadata }] }
//
// text_ur is all-or-nothing per chunk: it is built only when EVERY constituent
// English string has an exact-match translation in LEARN_UR; otherwise null
// (a half-translated chunk is worse than English).
import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import * as path from "node:path";

import { GLOSSARY } from "../src/finance-data";
import { LEARNING_PATHS } from "../src/learn-data";
import { LESSON_CONTENT } from "../src/lesson-content";
import type { ContentBlock, LessonContent, LessonSection } from "../src/lesson-content";
// Read-only import of the web-only translation map. Web is a sibling workspace
// package; this dev script deliberately reaches across via a relative path
// (shared must not depend on web at runtime — this never ships).
import { LEARN_UR } from "../../web/src/lib/learn/ur";

interface Chunk {
  source_type: "lesson_section" | "lesson_overview" | "glossary_term" | "quiz_explanation" | "learning_path";
  source_id: string;
  lesson_id: string | null;
  section_id: string | null;
  title: string;
  heading: string | null;
  text_en: string;
  text_ur: string | null;
  metadata: Record<string, unknown>;
}

/** Thrown by the Urdu transform when a constituent string has no translation. */
class MissingTranslation extends Error {}

type Tr = (s: string) => string;
const asEnglish: Tr = (s) => s;
const asUrdu: Tr = (s) => {
  const t = LEARN_UR[s];
  if (t === undefined) throw new MissingTranslation(s);
  return t;
};

/** Run a text builder with the Urdu transform; null if any constituent is untranslated. */
function urduOrNull(build: (tr: Tr) => string): string | null {
  try {
    return build(asUrdu);
  } catch (err) {
    if (err instanceof MissingTranslation) return null;
    throw err;
  }
}

function renderBlock(block: ContentBlock, tr: Tr): string {
  switch (block.type) {
    case "p":
    case "callout":
      return tr(block.text);
    case "formula":
      return block.lines.map(tr).join("\n");
    case "table":
      // Simple "col: val" lines per row; rows separated by a blank line.
      return block.rows
        .map((row) => block.head.map((col, i) => `${tr(col)}: ${tr(row[i] ?? "")}`).join("\n"))
        .join("\n\n");
  }
}

function renderSection(lesson: LessonContent, section: LessonSection, tr: Tr): string {
  // Context line so a chunk retrieved alone identifies itself.
  const context = `${tr(lesson.title)} — ${tr(section.heading)}`;
  const body = section.blocks.map((b) => renderBlock(b, tr)).join("\n\n");
  return `${context}\n\n${body}`;
}

function renderOverview(lesson: LessonContent, tr: Tr): string {
  // Table-of-contents style summary: title + section headings.
  return `${tr(lesson.title)}\n\n${lesson.sections.map((s) => tr(s.heading)).join("\n")}`;
}

function slug(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function sha1_12(s: string): string {
  return createHash("sha1").update(s, "utf8").digest("hex").slice(0, 12);
}

function buildChunks(): Chunk[] {
  const chunks: Chunk[] = [];

  for (const lesson of Object.values(LESSON_CONTENT)) {
    // lesson_section — one per section.
    for (const section of lesson.sections) {
      chunks.push({
        source_type: "lesson_section",
        source_id: `sec:${lesson.id}:${section.id}`,
        lesson_id: lesson.id,
        section_id: section.id,
        title: lesson.title,
        heading: section.heading,
        text_en: renderSection(lesson, section, asEnglish),
        text_ur: urduOrNull((tr) => renderSection(lesson, section, tr)),
        metadata: {},
      });
    }

    // lesson_overview — one per lesson.
    chunks.push({
      source_type: "lesson_overview",
      source_id: `lesson:${lesson.id}`,
      lesson_id: lesson.id,
      section_id: null,
      title: lesson.title,
      heading: null,
      text_en: renderOverview(lesson, asEnglish),
      text_ur: urduOrNull((tr) => renderOverview(lesson, tr)),
      metadata: {},
    });

    // quiz_explanation — one per quiz question (questions have no ids; key by sha1 of q).
    for (const question of lesson.quiz) {
      const render = (tr: Tr) =>
        `${tr(lesson.title)} — Quiz\n\n${tr(question.q)} Answer: ${tr(
          question.options[question.correct] ?? "",
        )}. ${tr(question.explanation)}`;
      chunks.push({
        source_type: "quiz_explanation",
        source_id: `quiz:${lesson.id}:${sha1_12(question.q)}`,
        lesson_id: lesson.id,
        section_id: null,
        title: lesson.title,
        heading: null,
        text_en: render(asEnglish),
        text_ur: urduOrNull(render),
        metadata: { question: question.q, correct_index: question.correct },
      });
    }
  }

  // glossary_term — one per term.
  for (const term of GLOSSARY) {
    const defUr = LEARN_UR[term.def];
    chunks.push({
      source_type: "glossary_term",
      source_id: `gloss:${slug(term.en)}`,
      lesson_id: null,
      section_id: null,
      title: term.en,
      heading: null,
      text_en: `${term.en}: ${term.def}`,
      // The Urdu term name alone is not a translation of the definition — only
      // emit text_ur when the definition itself is translated; otherwise keep
      // the Urdu name in metadata.term_ur.
      text_ur: defUr !== undefined ? `${term.ur}: ${defUr}` : null,
      metadata: defUr !== undefined ? {} : { term_ur: term.ur },
    });
  }

  // learning_path — one per path with at least one resolvable lesson.
  for (const p of LEARNING_PATHS) {
    const resolved = p.lessonIds.filter((id) => {
      if (LESSON_CONTENT[id]) return true;
      console.warn(
        `[export-learn-corpus] warning: path '${p.id}' references missing lesson '${id}' — skipped`,
      );
      return false;
    });
    if (resolved.length === 0) {
      console.warn(`[export-learn-corpus] warning: path '${p.id}' has no resolvable lessons — skipped`);
      continue;
    }
    const render = (tr: Tr) =>
      `${tr(p.title)}\n${tr(p.description)}\n\n${resolved
        .map((id, i) => `${i + 1}. ${tr(LESSON_CONTENT[id].title)}`)
        .join("\n")}`;
    chunks.push({
      source_type: "learning_path",
      source_id: `path:${p.id}`,
      lesson_id: null,
      section_id: null,
      title: p.title,
      heading: null,
      text_en: render(asEnglish),
      text_ur: urduOrNull(render),
      metadata: {},
    });
  }

  // Deterministic order: codepoint compare (NOT localeCompare — locale-dependent).
  chunks.sort((a, b) => (a.source_id < b.source_id ? -1 : a.source_id > b.source_id ? 1 : 0));
  return chunks;
}

function validate(chunks: Chunk[]): string[] {
  const errors: string[] = [];
  const seen = new Set<string>();
  for (const chunk of chunks) {
    if (seen.has(chunk.source_id)) errors.push(`duplicate source_id: ${chunk.source_id}`);
    seen.add(chunk.source_id);
    if (chunk.text_en.trim().length === 0) errors.push(`empty text_en: ${chunk.source_id}`);
  }
  return errors;
}

function main(): void {
  const chunks = buildChunks();

  const errors = validate(chunks);
  if (errors.length > 0) {
    console.error(`[export-learn-corpus] validation failed (${errors.length} error(s)):`);
    for (const e of errors) console.error(`  - ${e}`);
    process.exit(1);
  }

  const outDir = path.resolve(__dirname, "..", "..", "..", "..", "backend", "data");
  const outFile = path.join(outDir, "learn_corpus.json");
  mkdirSync(outDir, { recursive: true });
  writeFileSync(outFile, JSON.stringify({ version: 1, chunks }, null, 2) + "\n", "utf8");

  const counts = new Map<string, number>();
  for (const chunk of chunks) counts.set(chunk.source_type, (counts.get(chunk.source_type) ?? 0) + 1);
  const summary = [...counts.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([type, n]) => `${type}=${n}`)
    .join(" ");
  console.log(`[export-learn-corpus] wrote ${outFile}: ${summary} total=${chunks.length}`);
}

main();
