import { describe, expect, it, vi, afterEach } from "vitest";
import { API_BASE_URL } from "@/lib/api";
import {
  buildReportUrl,
  getDashboardRecommendation,
  generateStockReport,
  ReportError,
} from "./reports-client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function mockSessionToken(token: string | null) {
  vi.doMock("@/integrations/supabase/client", () => ({
    supabase: {
      auth: {
        getSession: async () => ({
          data: { session: token ? { access_token: token } : null },
        }),
      },
    },
  }));
}

function mockFetch(impl: Parameters<typeof vi.fn>[0]) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

describe("buildReportUrl", () => {
  it("appends lang= when the path has no query string", () => {
    expect(buildReportUrl("/api/ai/report/dashboard-recommendation", "en")).toBe(
      `${API_BASE_URL}/api/ai/report/dashboard-recommendation?lang=en`,
    );
  });

  it("uses & when the path already has a query string", () => {
    expect(buildReportUrl("/api/ai/report/portfolio?days=180", "ur")).toBe(
      `${API_BASE_URL}/api/ai/report/portfolio?days=180&lang=ur`,
    );
  });

  it("URI-encodes path segments (stock symbol)", () => {
    expect(buildReportUrl("/api/ai/report/stock/OGDC", "en")).toBe(
      `${API_BASE_URL}/api/ai/report/stock/OGDC?lang=en`,
    );
  });
});

describe("getDashboardRecommendation", () => {
  it("issues GET to /api/ai/report/dashboard-recommendation with the lang param", async () => {
    mockSessionToken("tok");
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        report_type: "dashboard_rec",
        content: {
          report_type: "dashboard_rec",
          schema_version: 1,
          lang: "en",
          headline: "Daily nudge",
          observations: ["You overspent on dining."],
          considerations: [],
          disclaimer: "Educational only.",
          citations: [],
        },
        provider: "groq",
        model: "llama",
        verified: true,
        created_at: null,
      }),
    });
    mockFetch(fetchMock);

    const res = await getDashboardRecommendation("en");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/ai/report/dashboard-recommendation?lang=en`);
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(res.content.headline).toBe("Daily nudge");
  });

  it("throws ReportError('auth') when no session", async () => {
    mockSessionToken(null);
    const fetchMock = vi.fn();
    mockFetch(fetchMock);

    await expect(getDashboardRecommendation("en")).rejects.toMatchObject({
      name: "ReportError",
      code: "auth",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps 429 to ReportError('quota')", async () => {
    mockSessionToken("tok");
    mockFetch(async () => ({ status: 429, ok: false, json: async () => ({}) }));
    await expect(getDashboardRecommendation("en")).rejects.toMatchObject({
      code: "quota",
      status: 429,
    });
  });

  it("maps 503 to ReportError('unavailable')", async () => {
    mockSessionToken("tok");
    mockFetch(async () => ({ status: 503, ok: false, json: async () => ({}) }));
    await expect(getDashboardRecommendation("en")).rejects.toMatchObject({ code: "unavailable" });
  });

  it("maps network failure to ReportError('network')", async () => {
    mockSessionToken("tok");
    mockFetch(async () => {
      throw new Error("ECONNREFUSED");
    });
    await expect(getDashboardRecommendation("en")).rejects.toMatchObject({ code: "network" });
  });
});

describe("generateStockReport", () => {
  it("POSTs to /api/ai/report/stock/{symbol} and uppercases the symbol in the URL", async () => {
    mockSessionToken("tok");
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({
        report_type: "stock_analysis",
        content: {
          report_type: "stock_analysis",
          schema_version: 1,
          lang: "en",
          symbol: "OGDC",
          headline: "OGDC snapshot",
          observations: ["OGDC traded at 145.30."],
          considerations: [],
          disclaimer: "Educational only.",
          citations: [],
        },
        provider: "gemini",
        model: "flash",
        verified: true,
        created_at: null,
      }),
    });
    mockFetch(fetchMock);

    const res = await generateStockReport("ogdc", "en");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE_URL}/api/ai/report/stock/OGDC?lang=en`);
    expect(init.method).toBe("POST");
    expect(res.content.symbol).toBe("OGDC");
  });
});

describe("ReportError", () => {
  it("preserves code and status", () => {
    const e = new ReportError("quota", "limit", 429);
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe("ReportError");
    expect(e.code).toBe("quota");
    expect(e.status).toBe(429);
    expect(e.message).toBe("limit");
  });
});
