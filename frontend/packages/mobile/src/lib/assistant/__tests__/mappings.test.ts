// The server speaks the web client's dialect; these lock the translation layer
// so executed actions actually refresh mobile caches and navs never crash.
import { mapInvalidateKeys, mapNavRoute } from "@/lib/assistant/mappings";

describe("mapInvalidateKeys", () => {
  it("maps every server key the backend tools can emit", () => {
    const all = [
      "finance-transactions",
      "finance-summary",
      "finance-budgets",
      "finance-bills",
      "finance-goals",
      "holdings",
      "portfolio-value",
      "portfolio-networth",
      "stock-transactions",
      "watchlist",
      "enriched-watchlist",
      "user-alerts",
      "price-alerts",
    ];
    for (const key of all) {
      expect(mapInvalidateKeys([key]).length).toBe(1);
    }
  });

  it("dedupes portfolio-flavored keys to one broad prefix", () => {
    const mapped = mapInvalidateKeys(["holdings", "portfolio-value", "portfolio-networth"]);
    expect(mapped).toEqual([["portfolio"]]);
  });

  it("skips unknown keys instead of guessing", () => {
    expect(mapInvalidateKeys(["something-new", "watchlist"])).toEqual([["watchlist"]]);
  });

  it("keeps narrow finance prefixes narrow", () => {
    expect(mapInvalidateKeys(["finance-budgets"])).toEqual([["finance", "budgets"]]);
    expect(mapInvalidateKeys(["finance-transactions"])).toEqual([["finance"]]);
  });
});

describe("mapNavRoute", () => {
  it("maps every backend nav destination or deliberately drops it", () => {
    expect(mapNavRoute("/app")).toBe("/(tabs)/app");
    expect(mapNavRoute("/finance")).toBe("/(tabs)/finance");
    expect(mapNavRoute("/portfolio")).toBe("/(tabs)/portfolio");
    expect(mapNavRoute("/psx")).toBe("/(tabs)/psx");
    expect(mapNavRoute("/learn")).toBe("/(tabs)/learn");
    expect(mapNavRoute("/watchlist")).toBe("/(tabs)/psx");
    expect(mapNavRoute("/alerts")).toBe("/alerts");
    expect(mapNavRoute("/settings")).toBe("/settings");
    expect(mapNavRoute("/funds")).toBe("/funds");
    expect(mapNavRoute("/dividends")).toBe("/dividends");
    // No mobile screens for these — dropped, mirroring the server's behavior.
    expect(mapNavRoute("/ai-insights")).toBeNull();
    expect(mapNavRoute("/monetary")).toBeNull();
    expect(mapNavRoute("/help")).toBeNull();
  });

  it("strips query strings and hashes defensively", () => {
    expect(mapNavRoute("/finance?tab=bills")).toBe("/(tabs)/finance");
    expect(mapNavRoute("/psx#screener")).toBe("/(tabs)/psx");
  });

  it("passes stock deep links through unchanged", () => {
    expect(mapNavRoute("/stock/HBL")).toBe("/stock/HBL");
    expect(mapNavRoute("/stock/../etc")).toBeNull();
  });
});
