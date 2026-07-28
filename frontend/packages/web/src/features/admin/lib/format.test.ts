/**
 * Formatting helpers used across every admin screen.
 *
 * The CSV cases matter most: an admin exports a table and opens it in Excel, so
 * a value that starts with `=` must not become a live formula, and Urdu display
 * names must not arrive mangled.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  toCsv,
  formatCompact,
  formatNumber,
  formatPercent,
  formatPkt,
  humanizeAction,
  humanizeKey,
  initials,
  relativeTime,
} from "./format";

describe("formatNumber / formatCompact / formatPercent", () => {
  it("renders an em dash for non-numbers rather than NaN", () => {
    for (const v of [null, undefined, "12", NaN, Infinity]) {
      expect(formatNumber(v)).toBe("—");
      expect(formatCompact(v)).toBe("—");
      expect(formatPercent(v)).toBe("—");
    }
  });

  it("keeps zero as a real value, not a dash", () => {
    // A metric block that genuinely counted zero must not look unavailable.
    expect(formatNumber(0)).toBe("0");
    expect(formatCompact(0)).toBe("0");
    expect(formatPercent(0)).toBe("0.0%");
  });

  it("groups thousands and compacts magnitudes", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatCompact(999)).toBe("999");
    expect(formatCompact(12400)).toBe("12.4K");
    expect(formatCompact(3_100_000)).toBe("3.1M");
  });
});

describe("formatPkt", () => {
  it("returns an em dash for missing or unparseable input", () => {
    expect(formatPkt(null)).toBe("—");
    expect(formatPkt(undefined)).toBe("—");
    expect(formatPkt("not-a-date")).toBe("—");
  });

  it("renders in Asia/Karachi regardless of the viewer's timezone", () => {
    // 2026-01-01T00:00:00Z is 05:00 on the 1st in PKT (UTC+5).
    const out = formatPkt("2026-01-01T00:00:00Z");
    expect(out).toContain("2026");
    expect(out).toContain("05:00");
  });

  it("can omit the time component", () => {
    expect(formatPkt("2026-01-01T00:00:00Z", false)).not.toContain(":");
  });
});

describe("relativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-28T12:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("describes recent and older instants", () => {
    expect(relativeTime("2026-07-28T11:59:30Z")).toBe("just now");
    expect(relativeTime("2026-07-28T11:30:00Z")).toBe("30m ago");
    expect(relativeTime("2026-07-28T06:00:00Z")).toBe("6h ago");
    expect(relativeTime("2026-07-25T12:00:00Z")).toBe("3d ago");
  });

  it("does not claim a future timestamp is in the past", () => {
    expect(relativeTime("2026-07-29T12:00:00Z")).toBe("in the future");
  });

  it("returns an em dash for missing input", () => {
    expect(relativeTime(null)).toBe("—");
  });
});

describe("humanize helpers", () => {
  it("turns audit action codes into prose without losing meaning", () => {
    expect(humanizeAction("admin.user.tier")).toBe("User tier");
    expect(humanizeAction("admin.flag.update")).toBe("Flag update");
  });

  it("turns metric keys into labels", () => {
    expect(humanizeKey("new_users_7d")).toBe("New users 7d");
  });
});

describe("initials", () => {
  it("derives initials from an email local part", () => {
    expect(initials("usman.tariq@x.com")).toBe("UT");
    expect(initials("admin@x.com")).toBe("AD");
  });

  it("never renders empty", () => {
    expect(initials(null)).toBe("?");
    expect(initials("")).toBe("?");
  });
});

describe("toCsv", () => {
  it("quotes values and doubles embedded quotes", () => {
    const out = toCsv(["a"], [['say "hi"']]);
    expect(out).toContain('"say ""hi"""');
  });

  it("neutralises spreadsheet formula injection", () => {
    // A display name of "=cmd|'/c calc'!A1" must not execute when opened in Excel.
    const out = toCsv(["name"], [["=1+1"], ["+x"], ["-x"], ["@x"]]);
    for (const prefixed of ['"\'=1+1"', '"\'+x"', '"\'-x"', '"\'@x"']) {
      expect(out).toContain(prefixed);
    }
  });

  it("prepends a BOM so Excel reads Urdu names as UTF-8", () => {
    expect(toCsv(["name"], [["عثمان"]]).startsWith("﻿")).toBe(true);
  });

  it("renders null as empty rather than the string 'null'", () => {
    expect(toCsv(["a"], [[null]])).not.toContain("null");
  });

  it("separates rows with CRLF per RFC 4180", () => {
    expect(toCsv(["a"], [["1"], ["2"]]).split("\r\n")).toHaveLength(3);
  });
});
