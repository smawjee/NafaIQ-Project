import { parseWebVtt } from "@/lib/vtt";

describe("parseWebVtt", () => {
  it("parses Studio captions with identifiers and strips formatting tags", () => {
    const source = [
      "WEBVTT",
      "",
      "intro",
      "00:00:00.000 --> 00:00:03.500",
      "Welcome to <b>NafaIQ</b>.",
      "",
      "00:03.500 --> 00:07.000 align:middle",
      "This lesson is source grounded.",
    ].join("\n");

    expect(parseWebVtt(source)).toEqual([
      { start: 0, end: 3.5, text: "Welcome to NafaIQ." },
      { start: 3.5, end: 7, text: "This lesson is source grounded." },
    ]);
  });
});
