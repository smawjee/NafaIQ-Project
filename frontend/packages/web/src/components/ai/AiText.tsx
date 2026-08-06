import { parseAiText, parseInline, type Span } from "@nafaiq/shared";

function renderSpans(items: Span[]) {
  return items.map((s, i) =>
    s.bold ? (
      <strong key={i} className="font-semibold">
        {s.text}
      </strong>
    ) : (
      <span key={i}>{s.text}</span>
    ),
  );
}

/**
 * One line of model-authored text (a headline, a bullet, a metric label).
 *
 * The report prompts ask for prose and never licensed markdown, but nothing
 * enforced that — so bold is rendered when it shows up and stray asterisks are
 * dropped, rather than either leaking to the reader.
 */
export function AiText({ text }: { text: string }) {
  return <>{renderSpans(parseInline(text))}</>;
}

/** Multi-paragraph model output: paragraphs and bullet lists. */
export function AiProse({ content }: { content: string }) {
  return (
    <div className="space-y-2">
      {parseAiText(content).map((b, i) =>
        b.kind === "ul" ? (
          <ul key={i} className="list-disc space-y-1 ps-4 marker:text-text-muted">
            {b.items.map((item, j) => (
              <li key={j}>{renderSpans(item)}</li>
            ))}
          </ul>
        ) : (
          <p key={i}>{renderSpans(b.spans)}</p>
        ),
      )}
    </div>
  );
}

/**
 * One tutor chat message. User messages pass through verbatim — only the model
 * is asked for formatting, and a learner typing `**` means `**`.
 */
export function TutorMessage({ content, role }: { content: string; role: "user" | "assistant" }) {
  if (role === "user") return <>{content}</>;
  return <AiProse content={content} />;
}
