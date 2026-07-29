import { describe, expect, it } from "vitest";
import { parseSseBuffer, type TutorEvent } from "./tutor-client";

describe("parseSseBuffer", () => {
  it("parses complete data blocks and keeps the partial tail", () => {
    const buffer =
      'data: {"type":"token","text":"Hello"}\n\n' +
      'data: {"type":"token","text":" PSX"}\n\n' +
      'data: {"type":"do'; // incomplete block
    const { events, rest } = parseSseBuffer(buffer);
    expect(events).toEqual<TutorEvent[]>([
      { type: "token", text: "Hello" },
      { type: "token", text: " PSX" },
    ]);
    expect(rest).toBe('data: {"type":"do');
  });

  it("parses done and error events", () => {
    const buffer =
      'data: {"type":"done","usage":{"used":4,"limit":10}}\n\n' +
      'data: {"type":"error","code":"quota","message":"limit"}\n\n';
    const { events, rest } = parseSseBuffer(buffer);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "done", usage: { used: 4, limit: 10 } });
    expect(events[1]).toEqual({ type: "error", code: "quota", message: "limit" });
    expect(rest).toBe("");
  });

  it("ignores non-data lines and malformed JSON", () => {
    const buffer = ': keep-alive\n\ndata: {broken\n\ndata: {"type":"token","text":"ok"}\n\n';
    const { events } = parseSseBuffer(buffer);
    expect(events).toEqual([{ type: "token", text: "ok" }]);
  });

  it("returns everything as rest when no complete block", () => {
    const { events, rest } = parseSseBuffer('data: {"type":"token"');
    expect(events).toEqual([]);
    expect(rest).toBe('data: {"type":"token"');
  });
});
