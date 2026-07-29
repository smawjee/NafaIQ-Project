import { describe, expect, it } from "vitest";
import { parseAiText, parseInline, type Block } from "@nafaiq/shared";

const text = (blocks: Block[]) =>
  blocks
    .map((b) =>
      b.kind === "p"
        ? b.spans.map((s) => s.text).join("")
        : b.items.map((i) => i.map((s) => s.text).join("")).join("|"),
    )
    .join("\n");

const flat = (spans: { text: string }[]) => spans.map((s) => s.text).join("");

describe("parseAiText", () => {
  it("renders **bold** as a bold span, not asterisks", () => {
    const [block] = parseAiText("Giants like **HBL** in banking.");
    expect(block).toEqual({
      kind: "p",
      spans: [
        { text: "Giants like ", bold: false },
        { text: "HBL", bold: true },
        { text: " in banking.", bold: false },
      ],
    });
  });

  it("never leaks a stray asterisk while a bold run is still streaming", () => {
    // Mid-stream the closing ** has not arrived. The learner must not see it.
    expect(text(parseAiText("Giants like **HBL"))).toBe("Giants like HBL");
    expect(text(parseAiText("A **b** and **c"))).toBe("A b and c");
  });

  it("groups consecutive bullets into one list and drops the markers", () => {
    const blocks = parseAiText("Weigh these:\n- Liquidity\n* Sector mix\n• Fees");
    expect(blocks.map((b) => b.kind)).toEqual(["p", "ul"]);
    expect(text(blocks)).toBe("Weigh these:\nLiquidity|Sector mix|Fees");
  });

  it("joins wrapped lines but splits paragraphs on a blank line", () => {
    expect(text(parseAiText("One line\nwrapped here.\n\nSecond para."))).toBe(
      "One line wrapped here.\nSecond para.",
    );
  });

  it("strips heading markers rather than shouting them", () => {
    expect(text(parseAiText("### The KSE-100"))).toBe("The KSE-100");
  });

  it("returns nothing for empty or whitespace-only output", () => {
    expect(parseAiText("")).toEqual([]);
    expect(parseAiText("\n  \n")).toEqual([]);
  });

  it("handles the real regression case end to end", () => {
    const blocks = parseAiText(
      "Giants from diverse sectors—like **HBL** in banking, **Engro** in fertilizers.",
    );
    expect(blocks).toHaveLength(1);
    expect(blocks[0].kind === "p" && blocks[0].spans.filter((s) => s.bold)).toEqual([
      { text: "HBL", bold: true },
      { text: "Engro", bold: true },
    ]);
    expect(text(blocks)).not.toContain("*");
  });
});

describe("parseInline", () => {
  // Report/LearnHub JSON fields are single prose strings, not documents.
  it("bolds inside a report headline and leaves no asterisks", () => {
    const spans = parseInline("**KSE-100** closed higher");
    expect(spans).toEqual([
      { text: "KSE-100", bold: true },
      { text: " closed higher", bold: false },
    ]);
  });

  it("keeps plain prose untouched", () => {
    expect(parseInline("Banks led the index today.")).toEqual([
      { text: "Banks led the index today.", bold: false },
    ]);
  });

  it("strips a stray heading marker from a field", () => {
    expect(flat(parseInline("## Key risk"))).toBe("Key risk");
  });

  it("survives an empty field", () => {
    expect(parseInline("")).toEqual([]);
  });
});
