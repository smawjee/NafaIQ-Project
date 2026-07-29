import { ReportError, reportErrorKey } from "@/lib/ai/reports-client";

describe("reportErrorKey", () => {
  it("maps a quota error to the upgrade message", () => {
    expect(reportErrorKey(new ReportError("quota", "x"))).toMatch(/limit/i);
  });

  it("maps an auth error to a sign-in prompt", () => {
    expect(reportErrorKey(new ReportError("auth", "x"))).toMatch(/sign in/i);
  });

  it("maps an unavailable error to try-again-shortly", () => {
    expect(reportErrorKey(new ReportError("unavailable", "x"))).toMatch(/temporarily/i);
  });

  it("falls back to a generic message for a non-ReportError", () => {
    expect(reportErrorKey(new Error("boom"))).toMatch(/try again/i);
  });

  it("carries the code and status on the error", () => {
    const e = new ReportError("quota", "Quota exceeded", 429);
    expect(e.code).toBe("quota");
    expect(e.status).toBe(429);
  });
});
