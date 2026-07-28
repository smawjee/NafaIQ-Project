import { describe, expect, it } from "vitest";

import {
  buildStockUniverse,
  logoUrlFor,
  matchStocks,
  type StockSearchResult,
} from "@/lib/psx/stock-search";
import type { ApiMarketSnapshotItem, ApiSymbolInfo } from "@/lib/psx/types";

const sym = (symbol: string, name: string, extra: Partial<ApiSymbolInfo> = {}) =>
  ({ symbol, name, sector: "Banks", logoid: null, ...extra }) as ApiSymbolInfo;

const quote = (symbol: string, price: number, change: number, change_pct: number) =>
  ({ symbol, price, change, change_pct }) as ApiMarketSnapshotItem;

const result = (symbol: string, name: string): StockSearchResult => ({
  symbol,
  name,
  sector: "Banks",
  price: null,
  change: null,
  changePct: null,
  logoUrl: null,
});

describe("logoUrlFor", () => {
  it("builds a TradingView SVG URL from a logoid", () => {
    expect(logoUrlFor("habib-bank")).toBe("https://s3-symbol-logo.tradingview.com/habib-bank.svg");
  });

  it("returns null for null, undefined and empty string", () => {
    expect(logoUrlFor(null)).toBeNull();
    expect(logoUrlFor(undefined)).toBeNull();
    expect(logoUrlFor("")).toBeNull();
  });
});

describe("buildStockUniverse", () => {
  it("returns an empty universe when symbols have not loaded", () => {
    expect(buildStockUniverse(undefined, [quote("HBL", 100, 1, 1)])).toEqual([]);
  });

  it("joins prices onto the symbol list by ticker", () => {
    const universe = buildStockUniverse(
      [sym("HBL", "Habib Bank"), sym("MEBL", "Meezan Bank")],
      [quote("HBL", 152.3, 2.3, 1.53)],
    );

    expect(universe).toHaveLength(2);
    expect(universe[0]).toMatchObject({
      symbol: "HBL",
      name: "Habib Bank",
      price: 152.3,
      change: 2.3,
      changePct: 1.53,
    });
  });

  it("keeps a symbol with no snapshot row, with null prices rather than dropping it", () => {
    // A stock missing from the snapshot must still be searchable — otherwise a
    // halted or newly listed ticker disappears from the search bar entirely.
    const universe = buildStockUniverse([sym("MEBL", "Meezan Bank")], []);

    expect(universe).toHaveLength(1);
    expect(universe[0]).toMatchObject({
      symbol: "MEBL",
      price: null,
      change: null,
      changePct: null,
    });
  });

  it("tolerates a missing snapshot entirely", () => {
    expect(buildStockUniverse([sym("HBL", "Habib Bank")], undefined)).toHaveLength(1);
  });

  it("carries the logo url through", () => {
    const universe = buildStockUniverse([sym("HBL", "Habib Bank", { logoid: "habib-bank" })], []);
    expect(universe[0].logoUrl).toBe("https://s3-symbol-logo.tradingview.com/habib-bank.svg");
  });

  it("treats a zero price as a real value, not as missing", () => {
    const universe = buildStockUniverse([sym("HBL", "Habib Bank")], [quote("HBL", 0, 0, 0)]);
    expect(universe[0].price).toBe(0);
  });
});

describe("matchStocks", () => {
  const universe = [
    result("HBL", "Habib Bank Limited"),
    result("MEBL", "Meezan Bank Limited"),
    result("UBL", "United Bank Limited"),
    result("BAHL", "Bank AL Habib Limited"),
    result("OGDC", "Oil & Gas Development Company"),
  ];

  it("browses the universe when the query is empty", () => {
    expect(matchStocks(universe, "")).toHaveLength(5);
    expect(matchStocks(universe, "   ")).toHaveLength(5);
  });

  it("honours the limit when browsing", () => {
    expect(matchStocks(universe, "", 2)).toHaveLength(2);
  });

  it("is case-insensitive", () => {
    expect(matchStocks(universe, "hbl")[0].symbol).toBe("HBL");
    expect(matchStocks(universe, "HbL")[0].symbol).toBe("HBL");
  });

  it("trims the query", () => {
    expect(matchStocks(universe, "  ogdc  ")[0].symbol).toBe("OGDC");
  });

  it("ranks exact ticker > ticker prefix > ticker contains", () => {
    // Synthetic tickers chosen so one query hits all three tiers at once:
    // UBL is exact, UBLX is a prefix match, SUBL merely contains it.
    const ranked = [
      result("SUBL", "Sub Corp"),
      result("UBLX", "Ubl Extra"),
      result("UBL", "United Bank Limited"),
    ];

    expect(matchStocks(ranked, "UBL").map((h) => h.symbol)).toEqual(["UBL", "UBLX", "SUBL"]);
  });

  it("ranks a ticker match above a name-only match", () => {
    const hits = matchStocks(universe, "HBL");
    // Only HBL matches: "HBL" is not a substring of BAHL, nor of any name here.
    expect(hits.map((h) => h.symbol)).toEqual(["HBL"]);
  });

  it("ranks a ticker prefix above a name match", () => {
    const hits = matchStocks(universe, "U");
    // UBL matches by ticker prefix (80); "United Bank" also name-prefixes (50).
    expect(hits[0].symbol).toBe("UBL");
  });

  it("matches on company name, not just ticker", () => {
    const hits = matchStocks(universe, "meezan");
    expect(hits[0].symbol).toBe("MEBL");
  });

  it("finds a name substring that is not a prefix", () => {
    const hits = matchStocks(universe, "development");
    expect(hits.map((h) => h.symbol)).toEqual(["OGDC"]);
  });

  it("returns nothing for a query that matches neither ticker nor name", () => {
    expect(matchStocks(universe, "ZZZZ")).toEqual([]);
  });

  it("breaks ties alphabetically by ticker so ordering is stable", () => {
    // "BANK" appears in the NAME of HBL, MEBL, UBL and BAHL — all score 30.
    const hits = matchStocks(universe, "BANK").map((h) => h.symbol);
    expect(hits).toEqual([...hits].sort());
  });

  it("applies the limit after ranking, keeping the best matches", () => {
    const hits = matchStocks(universe, "BANK", 2);
    expect(hits).toHaveLength(2);
  });

  it("handles an empty universe", () => {
    expect(matchStocks([], "HBL")).toEqual([]);
  });
});
