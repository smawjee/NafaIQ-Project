// Parses the light markdown the LLM emits into renderable blocks/spans.
//
// Why this exists: prompts/tutor.txt asks the model for "short paragraphs or a
// few bullets" and **bold**, so it emits markdown by design. Every surface used
// to render the raw string, so learners saw literal asterisks and collapsed
// newlines. The report/LearnHub prompts never forbade markdown either, so their
// JSON string fields may contain it too.
//
// This is NOT a markdown implementation. It handles bold, "- " bullets, and
// paragraphs — the subset the prompts actually license — and strips anything
// else. That is deliberate: this is untrusted model text, and callers render it
// into React/RN elements, so there is no dangerouslySetInnerHTML and no
// sanitiser to get wrong. Adding links or images here would change that.
//
// Lives in shared because web renders <strong> and mobile renders a nested RN
// <Text>: only the PARSE is common, and it must not drift from the prompt
// contract on one platform but not the other.
// ponytail: hand parser over a react-markdown dep; revisit if the tutor ever
// needs links or code blocks, which would make a real renderer worth the weight.

export type Span = { text: string; bold: boolean };
export type Block = { kind: "p"; spans: Span[] } | { kind: "ul"; items: Span[][] };

const BULLET = /^\s*[-*•]\s+/;
const HEADING = /^\s*#{1,6}\s+/;
const BOLD_PAIR = /\*\*([\s\S]+?)\*\*/g;

/**
 * Split one line into bold/plain spans.
 *
 * Only *matched* `**` pairs become bold. Leftover asterisks are stripped rather
 * than shown: mid-stream the closing `**` has not arrived yet, and a learner
 * should never watch raw syntax type itself out and then vanish.
 */
export function parseSpans(line: string): Span[] {
  const spans: Span[] = [];
  let last = 0;

  for (const m of line.matchAll(BOLD_PAIR)) {
    const plain = line.slice(last, m.index);
    if (plain) spans.push({ text: plain, bold: false });
    spans.push({ text: m[1], bold: true });
    last = m.index + m[0].length;
  }

  const tail = line.slice(last);
  if (tail) spans.push({ text: tail, bold: false });

  return spans
    .map((s) => (s.bold ? s : { ...s, text: s.text.replace(/\*+/g, "") }))
    .filter((s) => s.text !== "");
}

/**
 * Parse a single-line/inline field (a headline, a bullet, a metric label) into
 * spans. Use for the report JSON fields, which are prose, not documents.
 */
export function parseInline(text: string): Span[] {
  return parseSpans(text.replace(HEADING, "").trim());
}

/**
 * Parse multi-paragraph model output into blocks.
 *
 * Consecutive bullet lines collapse into one list; consecutive prose lines join
 * into one paragraph (the model wraps mid-sentence, so a bare newline is not a
 * break); a blank line starts a new paragraph.
 */
export function parseAiText(content: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: Span[][] | null = null;

  const flushPara = () => {
    if (para.length) blocks.push({ kind: "p", spans: parseSpans(para.join(" ")) });
    para = [];
  };
  const flushList = () => {
    if (list?.length) blocks.push({ kind: "ul", items: list });
    list = null;
  };

  for (const raw of content.split("\n")) {
    const line = raw.trim();

    if (!line) {
      flushPara();
      flushList();
      continue;
    }

    if (BULLET.test(line)) {
      flushPara();
      const spans = parseSpans(line.replace(BULLET, ""));
      if (spans.length) (list ??= []).push(spans);
      continue;
    }

    flushList();
    // Headings are stripped to plain prose: the bubbles are ~88% of a narrow
    // panel, so a real <h*> would just be shouting.
    para.push(line.replace(HEADING, ""));
  }

  flushPara();
  flushList();
  return blocks.filter((b) => (b.kind === "p" ? b.spans.length > 0 : b.items.length > 0));
}
