import { describe, expect, it } from "vitest";
import { formatMonthKey, monthRangeLabel } from "@/lib/finance/range";

describe("formatMonthKey", () => {
  it("expands an API month key", () => {
    expect(formatMonthKey("2026-03")).toBe("Mar 2026");
    expect(formatMonthKey("2026-08")).toBe("Aug 2026");
    expect(formatMonthKey("2026-12")).toBe("Dec 2026");
    expect(formatMonthKey("2026-01")).toBe("Jan 2026");
  });

  it("passes a demo fixture month through unchanged", () => {
    // The demo series uses bare names; mangling them would be a new bug.
    expect(formatMonthKey("Jan")).toBe("Jan");
  });

  it("passes an unparseable key through rather than inventing a month", () => {
    expect(formatMonthKey("2026-13")).toBe("2026-13");
    expect(formatMonthKey("")).toBe("");
  });
});

describe("monthRangeLabel", () => {
  it("labels the real range shown on the axis", () => {
    // The regression: the caption read a hard-coded "Jan 2026 — Jun 2026"
    // while the axis ran 2026-03 .. 2026-08.
    const months = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"];
    expect(monthRangeLabel(months)).toBe("Mar 2026 — Aug 2026");
  });

  it("spans a year boundary", () => {
    expect(monthRangeLabel(["2025-11", "2025-12", "2026-01"])).toBe("Nov 2025 — Jan 2026");
  });

  it("collapses a single month to one label", () => {
    expect(monthRangeLabel(["2026-08"])).toBe("Aug 2026");
  });

  it("returns an empty string for an empty series", () => {
    expect(monthRangeLabel([])).toBe("");
  });

  it("handles the demo fixture", () => {
    expect(monthRangeLabel(["Jan", "Feb", "Mar"])).toBe("Jan — Mar");
  });
});
