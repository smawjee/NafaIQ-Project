import { Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Sparkles, Plus, Star, Filter, CandlestickChart as CandleIcon, Grid3x3, List, LayoutGrid, Flame } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { toast } from "sonner";

import { Card } from "@/components/shared/Card";
import { InfoTip } from "@/components/shared/InfoTip";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { Change } from "@/components/market/Change";
import { SignalBadge } from "@/components/market/SignalBadge";
import { CandlestickChart, PriceLineChart, Sparkline } from "@/components/charts/charts";
import { ChartToolbar, type Indicator, type Timeframe } from "@/components/charts/ChartToolbar";
import { INDICES, STOCKS, STOCK_LIST, generateOHLCV, sma, fmtNum, type Signal } from "@/lib/data";
import {
  usePsxLiveMarket,
  usePsxRealtime,
  usePsxHistory,
  usePsxSymbols,
  usePsxIndexData,
  usePsxBatchSignals,
  usePsxScreenerMetrics,
  usePsxTreemap,
  useMarketMovers,
  useIndexCards,
} from "@/hooks/psx/use-psx";
import { usePersistedTfMap } from "@/hooks/psx/use-persisted-tf-map";
import { formatNumber, formatCompactPKR } from "@/lib/format";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { useDemo } from "@/hooks/use-demo";
import { StatsGridSkeleton, ChartSkeleton, TableSkeleton } from "@/components/shared/PageSkeleton";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { MarketTicker } from "@/features/psx/components/MarketTicker";
import { Treemap } from "@/features/heatmap/Treemap";
import { HeatmapLegend } from "@/features/heatmap/HeatmapLegend";
import { HeatmapSkeleton } from "@/features/heatmap/HeatmapSkeleton";
import { HeatmapEmptyState } from "@/features/heatmap/HeatmapEmptyState";
import { TopMoversView } from "@/features/heatmap/TopMoversView";
import { SYMBOLS, INDEX_INFO } from "@/features/psx/psx.data";
import { tfDays, symbolMeta } from "@/features/psx/psx.utils";

export function PSX() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [sym, setSym] = useState("KSE-100");
  const { tfFor, setTfFor } = usePersistedTfMap("6M");
  const tf = tfFor(sym) as Timeframe;
  const setTf = (next: Timeframe) => setTfFor(sym, next);
  const [type, setType] = useState<"candle" | "line">("candle");
  const [mas, setMas] = useState<Indicator[]>(["MA20", "MA50", "MA100"]);
  const [moverTab, setMoverTab] = useState<"Gainers" | "Losers" | "Most Active">("Gainers");
  const [signalFilter, setSignalFilter] = useState<string>("All");
  const [sectorFilter, setSectorFilter] = useState<string>("All");
  const [searchFilter, setSearchFilter] = useState("");
  const [screenerPage, setScreenerPage] = useState(1);
  const [showAllIndices, setShowAllIndices] = useState(false);
  const [heatmapView, setHeatmapView] = useState<"treemap" | "sectors" | "movers">("treemap");
  const [drilledSector, setDrilledSector] = useState<string | null>(null);
  const [heatmapSort, setHeatmapSort] = useState<"cap" | "change" | "volume">("cap");
  const watchlist = useWatchlist();
  const { isDemo } = useDemo();
  const [addOpen, setAddOpen] = useState(false);
  const { data: snapshot, isLoading: snapshotLoading } = usePsxLiveMarket();
  // Phase 0 / B8: scope the realtime channel to this user's watchlist. The
  // /psx page keeps using the global snapshot, so we still re-render the
  // table on changes — but the per-row update path no longer floods the
  // browser for stocks the user isn't watching.
  usePsxRealtime(watchlist.symbols);
  const { data: ohlcvData } = usePsxHistory(sym === "KSE-100" ? "KSE100" : sym, Math.max(365, tfDays(tf)));
  const { data: symbolsData } = usePsxSymbols();
  const { data: kse100Data } = usePsxIndexData("KSE100");
  const { data: batchSignals } = usePsxBatchSignals(50);
  const { data: screenerMetrics } = usePsxScreenerMetrics();
  const { data: treemapData, isLoading: isLoadingTreemap } = usePsxTreemap();
  const marketMovers = useMarketMovers(
    moverTab === "Gainers" ? "gainers" : moverTab === "Losers" ? "losers" : "volume",
    6,
  );
  const indexCardsAll = useIndexCards(18);
  // Pick the priority 4 (KSE-100, KSE-30, KMI-30, KSE All Share) when not
  // expanded. The hook itself already orders priority-first; slice(0, 4)
  // gives us the dashboard subset without a second render path.
  const indexCards = useMemo(() => showAllIndices ? indexCardsAll : indexCardsAll.slice(0, 4), [showAllIndices, indexCardsAll]);

  const getSparkline = useCallback((ic: { name: string; value: number; change: number; changePct: number }, index: number) => {
    if (ic.name === "KSE-100" && kse100Data && kse100Data.length >= 7) {
      return kse100Data.slice(-7).map(d => d.close);
    }
    // Generate a plausible 7-day trend based on current value and daily change
    const step = ic.change / 6 || 0;
    return Array.from({ length: 7 }, (_, i) => ic.value - step * (6 - i));
  }, [kse100Data]);

  const displayIndices = useMemo(() => {
    if (indexCards.length > 0) {
      return indexCards.map((ic, i) => ({
        key: ic.name,
        name: ic.name,
        value: ic.value,
        change: ic.change,
        changePct: ic.changePct,
        spark: getSparkline(ic, i),
      }));
    }
    return INDICES.map((idx) => ({
      key: idx.name,
      name: idx.name,
      value: idx.value,
      change: idx.change,
      changePct: idx.changePct,
      spark: generateOHLCV(idx.seed, idx.start, idx.end, 7).map((c) => c.close),
    }));
  }, [indexCards, getSparkline]);


  const visibleCount = tfDays(tf);

  const full = useMemo(() => {
    const asc = <T extends { date: string }>(rows: T[]) =>
      [...rows].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    // KSE-100 is an index: its real candles live in psx_index_eod, never psx_ohlcv.
    if (sym === "KSE-100") {
      if (kse100Data && kse100Data.length > 0) {
        return asc(kse100Data).map((b) => ({
          date: b.date,
          t: new Date(b.date).getTime(),
          open: b.open ?? b.close,
          high: b.high ?? b.close,
          low: b.low ?? b.close,
          close: b.close,
          volume: b.volume ?? 0,
        }));
      }
    } else if (ohlcvData && ohlcvData.length > 0) {
      // Real OHLCV, oldest -> newest, most recent 250 bars.
      return asc(ohlcvData).slice(-250);
    }
    // Demo users see realistic generated candles; real users never see dummy data
    // (an empty array renders a clean "no data" state below).
    if (isDemo) {
      const meta = symbolMeta(sym);
      return generateOHLCV(meta.seed, meta.start, meta.end, 250, meta.vMin, meta.vMax);
    }
    return [];
  }, [sym, ohlcvData, kse100Data, isDemo]);

  // Phase 0 / B3: detect "OHLC columns are all-null" (true for many index EOD
  // rows from DPS). In that case, fall back to a line chart so the user sees a
  // real curve instead of a row of flat dojis.
  const allIndexOhlcNull = useMemo(() => {
    if (sym !== "KSE-100") return false;
    if (full.length === 0) return false;
    // Any non-null open/high/low means we have real candles.
    return full.every((b) => b.open === b.high && b.high === b.low && b.low === b.close);
  }, [sym, full]);
  const effectiveType = allIndexOhlcNull ? "line" : type;
  const liveIndexClose = full.length > 0 ? full[full.length - 1].close : null;

  const data = full.slice(-visibleCount);
  const hasData = data.length > 0;
  // Compute MAs over the full 250-point series (so MA200 warms up), then align
  // to the visible window — otherwise short timeframes render an empty MA line.
  const maSeries = useMemo(() => {
    const start = Math.max(0, full.length - visibleCount);
    return {
      ma20: sma(full, 20).slice(start),
      ma50: sma(full, 50).slice(start),
      ma100: sma(full, 100).slice(start),
      ma200: sma(full, 200).slice(start),
    };
  }, [full, visibleCount]);
  const last = data[data.length - 1];
  const first = data[0];
  const chg = hasData ? last.close - first.open : 0;
  const chgPct = hasData && first.open ? (chg / first.open) * 100 : 0;

  const metricsMap = useMemo(() => {
    const m = new Map<string, { rsi: number | null; market_cap: number | null }>();
    for (const row of screenerMetrics ?? []) {
      m.set(row.symbol, { rsi: row.rsi, market_cap: row.market_cap });
    }
    return m;
  }, [screenerMetrics]);

  const screenRows = useMemo(() => {
    const sectorMap = new Map<string, string>();
    if (symbolsData) {
      for (const s of symbolsData) {
        sectorMap.set(s.symbol, s.sector ?? "—");
      }
    }
    if (snapshot && snapshot.length > 0) {
      const signalMap = new Map<string, Signal>();
      if (batchSignals?.signals) {
        for (const s of batchSignals.signals) {
          if (s.signal) signalMap.set(s.symbol, s.signal as Signal);
        }
      }
      let rows = snapshot.map((s) => {
        const m = metricsMap.get(s.symbol);
        return {
          ticker: s.symbol,
          sector: sectorMap.get(s.symbol) ?? "—",
          price: s.price ?? 0,
          changePct: s.change_pct ?? 0,
          // No fabricated HOLD: only show a signal the model actually produced.
          signal: signalMap.get(s.symbol) ?? null,
          rsi: m?.rsi ?? null,
          volume: formatNumber(s.volume ?? 0, 0),
          marketCap: m?.market_cap != null ? formatCompactPKR(m.market_cap) : "—",
        };
      });
      if (sectorFilter !== "All") {
        rows = rows.filter((r) => r.sector === sectorFilter);
      }
      if (searchFilter) {
        const q = searchFilter.toUpperCase();
        rows = rows.filter((r) => r.ticker.includes(q) || r.sector.toUpperCase().includes(q));
      }
      return rows;
    }
    // Real users never see fabricated rows — only demo falls back to the static list.
    if (!isDemo) return [];
    return STOCK_LIST.map((s) => ({
      ...s,
      rsi: s.rsi as number | null,
      signal: s.signal as Signal | null,
    }));
  }, [snapshot, symbolsData, sectorFilter, searchFilter, batchSignals, metricsMap, isDemo]);

  const movers = useMemo(() => {
    if (marketMovers.length > 0) {
      const signalMap = new Map<string, Signal>();
      if (batchSignals?.signals) {
        for (const s of batchSignals.signals) {
          if (s.signal) signalMap.set(s.symbol, s.signal as Signal);
        }
      }
      return marketMovers.map((m) => ({
        ticker: m.symbol,
        sector: m.sector,
        price: m.price,
        changePct: m.changePct,
        signal: signalMap.get(m.symbol) ?? null,
        rsi: metricsMap.get(m.symbol)?.rsi ?? null,
        volume: formatNumber(m.volume ?? 0, 0),
        marketCap:
          metricsMap.get(m.symbol)?.market_cap != null
            ? formatCompactPKR(metricsMap.get(m.symbol)!.market_cap!)
            : "—",
      }));
    }
    // Real users never see fabricated movers — only demo falls back.
    if (!isDemo) return [];
    const arr = [...STOCK_LIST];
    if (moverTab === "Gainers")
      return arr
        .filter((s) => s.changePct > 0)
        .sort((a, b) => b.changePct - a.changePct)
        .slice(0, 6);
    if (moverTab === "Losers") return arr.sort((a, b) => a.changePct - b.changePct).slice(0, 6);
    return arr.sort((a, b) => parseFloat(b.volume) - parseFloat(a.volume)).slice(0, 6);
  }, [moverTab, marketMovers, batchSignals, metricsMap, isDemo]);

  const screened = screenRows.filter((s) => signalFilter === "All" || s.signal === signalFilter);
  const screenerPageSize = 8;
  const screenerPageCount = Math.max(1, Math.ceil(screened.length / screenerPageSize));
  const currentScreenerPage = Math.min(screenerPage, screenerPageCount);
  const visibleScreened = screened.slice(
    (currentScreenerPage - 1) * screenerPageSize,
    currentScreenerPage * screenerPageSize,
  );
  const screenerStart =
    screened.length === 0 ? 0 : (currentScreenerPage - 1) * screenerPageSize + 1;
  const screenerEnd = Math.min(currentScreenerPage * screenerPageSize, screened.length);

  const sortedTreemapData = useMemo(() => {
    if (!treemapData) return null;
    if (heatmapSort === "cap") return treemapData; // already sorted by market cap

    const sortKey = heatmapSort === "change"
      ? (a: typeof treemapData.sectors[0], b: typeof treemapData.sectors[0]) => Math.abs(b.avg_change_pct) - Math.abs(a.avg_change_pct)
      : (a: typeof treemapData.sectors[0], b: typeof treemapData.sectors[0]) => b.total_market_cap - a.total_market_cap;

    return {
      ...treemapData,
      sectors: [...treemapData.sectors].sort(sortKey),
    };
  }, [treemapData, heatmapSort]);

  useEffect(() => {
    setScreenerPage(1);
  }, [searchFilter, sectorFilter, signalFilter]);

  if (snapshotLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-6">
        <MarketTicker />
        <StatsGridSkeleton count={4} />
        <div className="grid min-w-0 gap-6 lg:grid-cols-[65fr_35fr]">
          <div className="min-w-0 space-y-4">
            <ChartSkeleton className="h-[480px]" />
            <ChartSkeleton className="h-24" />
            <TableSkeleton rows={5} />
          </div>
          <div className="min-w-0 space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <ChartSkeleton key={i} className="h-64" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Live market ticker — always-dark dense data strip */}
      <MarketTicker />

      {/* Index overview */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-primary">{t("Indices")}</h3>
          {indexCardsAll.length > 4 && (
            <button
              type="button"
              onClick={() => setShowAllIndices((v) => !v)}
              className="shrink-0 rounded-[6px] border border-border px-2 py-1 text-xs font-medium text-text-secondary hover:bg-hover hover:text-text-primary"
            >
              {showAllIndices ? t("Show 4") : t("Show all")}
            </button>
          )}
        </div>
        <div
          className={cn(
            "grid gap-4",
            showAllIndices
              ? // 18 cards laid out in 3 rows of 6 on lg — wide enough to keep
                // each card's chart + number legible, dense enough to compare
                // the whole market at a glance.
                "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6"
              : "grid-cols-2 lg:grid-cols-4",
          )}
        >
          {displayIndices.map((idx) => (
            <Card key={idx.key}>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-text-secondary">{idx.name}</span>
                {INDEX_INFO[idx.name] && <InfoTip label={INDEX_INFO[idx.name]} />}
              </div>
              <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
                <CountUpNumber value={idx.value} decimals={2} />
              </div>
              <div className="flex items-center justify-between">
                <Change
                  value={`${idx.change >= 0 ? "+" : ""}${fmtNum(idx.change)}`}
                  pct={idx.changePct}
                />
              </div>
              <div className="mt-1">
                <Sparkline data={idx.spark} color="#00d4aa" />
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div className="grid min-w-0 gap-6 lg:grid-cols-[65fr_35fr]">
        {/* Chart column */}
        <div className="min-w-0 space-y-4">
          <Card hover={false} className="bg-surface-alt p-3">
            {/* Phase 0 / B6+B7: unified chart toolbar with a searchable stock picker */}
            <ChartToolbar
              sym={sym}
              nameFor={(s) => STOCKS[s]?.name ?? s}
              onSymChange={setSym}
              tf={tf}
              onTfChange={setTf}
              type={type}
              onTypeChange={setType}
              mas={mas}
              onMasChange={setMas}
            />

            {hasData ? (
              <>
                {/* Price overlay */}
                <div className="mb-2 flex flex-wrap items-baseline gap-3">
                  <span className="font-mono text-2xl font-bold tabular-nums text-text-primary">
                    {fmtNum(last.close)}
                  </span>
                  <Change value={`${chg >= 0 ? "+" : ""}${fmtNum(chg)}`} pct={chgPct} />
                  <span className="font-mono text-xs tabular-nums text-text-muted">
                    O {fmtNum(first.open)} · H {fmtNum(Math.max(...data.map((d) => d.high)))} · L{" "}
                    {fmtNum(Math.min(...data.map((d) => d.low)))} · Vol {last.volume}M
                  </span>
                </div>

                <div className="h-[300px] lg:h-[480px]">
                  {effectiveType === "line" ? (
                    <PriceLineChart key={sym} data={data} height={9999} mas={mas} maSeries={maSeries} />
                  ) : (
                    <CandlestickChart key={sym} data={data} height={9999} mas={mas} maSeries={maSeries} />
                  )}
                </div>
                {allIndexOhlcNull && liveIndexClose != null && (
                  <p className="mt-2 text-[11px] text-text-muted">
                    {t(
                      "Index OHLC is daily-only — showing a close line. Live tick is the latest point.",
                    )}
                  </p>
                )}
              </>
            ) : (
              <div className="flex h-[300px] flex-col items-center justify-center gap-2 text-center lg:h-[480px]">
                <CandleIcon className="h-8 w-8 text-text-muted" />
                <p className="text-sm text-text-secondary">
                  {t("No chart data available for")} {sym}
                </p>
                <p className="text-xs text-text-muted">
                  {t("Historical prices haven't been loaded for this symbol yet.")}
                </p>
              </div>
            )}
          </Card>

          {/* AI signal bar */}
          <div className="rounded-[8px] border border-border border-l-4 border-l-ai bg-ai-tint p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center">
              <div className="flex items-center gap-2 text-sm font-semibold text-ai">
                <Sparkles className="h-4 w-4" />
                {t("AI Analysis")}
              </div>
              <p className="flex-1 text-xs leading-relaxed text-text-secondary">
                <Typewriter
                  id="psx-ai-analysis"
                  text={t(
                    "KSE-100 is trading above MA20, MA50 and MA100 with strong volume confirmation. RSI at 58 — bullish momentum without being overbought. Banking and Tech sectors leading gains today.",
                  )}
                />
              </p>
              <div className="text-right">
                <SignalBadge signal="STRONG BUY" />
                <div className="mt-1 text-xs font-medium text-bull">
                  {t("BULLISH · Confidence 72%")}
                </div>
              </div>
            </div>
            <p className="mt-2 text-[10px] italic text-text-muted">
              {t("Based on technical indicators only. Not financial advice.")}
            </p>
          </div>

          {/* Stock Screener */}
          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">{t("Stock Screener")}</h3>
                <p className="text-[11px] text-text-muted">
                  {screened.length > 0
                    ? `${t("Showing")} ${screenerStart}-${screenerEnd} ${t("of")} ${screened.length}`
                    : t("No stocks match the selected filters.")}
                </p>
              </div>
              <div className="flex items-center gap-1 text-xs text-text-secondary">
                <button
                  type="button"
                  disabled={currentScreenerPage <= 1}
                  onClick={() => setScreenerPage((p) => Math.max(1, p - 1))}
                  className="rounded-[6px] border border-border px-2 py-1 hover:bg-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {t("Prev")}
                </button>
                <span className="min-w-12 text-center font-mono tabular-nums">
                  {currentScreenerPage}/{screenerPageCount}
                </span>
                <button
                  type="button"
                  disabled={currentScreenerPage >= screenerPageCount}
                  onClick={() => setScreenerPage((p) => Math.min(screenerPageCount, p + 1))}
                  className="rounded-[6px] border border-border px-2 py-1 hover:bg-hover disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {t("Next")}
                </button>
              </div>
            </div>
            <div className="mb-3 flex items-center gap-2">
              <Filter className="h-4 w-4 text-text-secondary" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder={t("Search symbol or sector...")}
                className="min-w-0 flex-1 rounded-[6px] border border-border bg-elevated px-2.5 py-1 text-xs text-text-primary placeholder:text-text-muted"
              />
              <select
                value={sectorFilter}
                onChange={(e) => setSectorFilter(e.target.value)}
                className="rounded-[6px] border border-border bg-elevated px-2 py-1 text-xs font-medium text-text-primary"
              >
                <option value="All">{t("All Sectors")}</option>
                {(() => {
                  const uniqSectors = new Set<string>();
                  if (symbolsData) {
                    for (const s of symbolsData) {
                      if (s.sector) uniqSectors.add(s.sector);
                    }
                  }
                  return Array.from(uniqSectors)
                    .sort()
                    .map((sec) => (
                      <option key={sec} value={sec}>
                        {t(sec)}
                      </option>
                    ));
                })()}
              </select>
            </div>
            <div className="mb-3 flex flex-wrap gap-1.5">
              {(
                ["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"] as (string | Signal)[]
              ).map((f) => (
                <button
                  key={f}
                  onClick={() => setSignalFilter(f)}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    signalFilter === f
                      ? "bg-bull text-bull-foreground"
                      : "border border-border text-text-secondary hover:bg-hover",
                  )}
                >
                  {t(f)}
                </button>
              ))}
            </div>
            <div className="scrollbar-none overflow-x-auto">
              <table className="w-full min-w-[640px] text-xs">
                <thead>
                  <tr className="border-b border-border text-left text-text-muted">
                    <th className="py-2">{t("Stock")}</th>
                    <th>{t("Sector")}</th>
                    <th className="text-right">{t("Price")}</th>
                    <th className="text-right">{t("Change")}</th>
                    <th className="text-center">{t("Signal")}</th>
                    <th className="text-right">RSI</th>
                    <th className="text-right">{t("Volume")}</th>
                    <th className="pr-2 text-right">{t("Mkt Cap")}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleScreened.map((s, i) => (
                    <tr
                      key={s.ticker}
                      className={cn("cursor-pointer hover:bg-hover", i % 2 ? "bg-surface-alt" : "")}
                    >
                      <td className="py-2">
                        <Link
                          to="/stock/$ticker"
                          params={{ ticker: s.ticker }}
                          className="font-semibold text-bull"
                        >
                          {s.ticker}
                        </Link>
                      </td>
                      <td className="text-text-secondary">{t(s.sector)}</td>
                      <td className="text-right font-mono tabular-nums text-text-primary">
                        {fmtNum(s.price)}
                      </td>
                      <td className="text-right">
                        <Change pct={s.changePct} />
                      </td>
                      <td className="text-center">
                        {s.signal ? (
                          <SignalBadge signal={s.signal} />
                        ) : (
                          <span className="text-text-muted" title={t("Signal unavailable")}>
                            —
                          </span>
                        )}
                      </td>
                      <td className="text-right font-mono tabular-nums">
                        {s.rsi == null ? (
                          <span className="text-text-muted" title={t("Not enough history")}>
                            —
                          </span>
                        ) : (
                          <span
                            className={cn(
                              s.rsi > 70
                                ? "text-bear"
                                : s.rsi < 30
                                  ? "text-bull"
                                  : "text-text-secondary",
                            )}
                            title={
                              s.rsi > 70
                                ? t("Overbought")
                                : s.rsi < 30
                                  ? t("Oversold")
                                  : t("Neutral")
                            }
                          >
                            {s.rsi.toFixed(0)}
                            {s.rsi > 70 ? " OB" : s.rsi < 30 ? " OS" : ""}
                          </span>
                        )}
                      </td>
                      <td className="text-right font-mono tabular-nums text-text-secondary">
                        {s.volume}
                      </td>
                      <td className="pr-2 text-right font-mono tabular-nums text-text-secondary">
                        {s.marketCap}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* Right panel */}
        <div className="min-w-0 space-y-4">
          <Card>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">{t("Watchlist")}</h3>
              <Popover open={addOpen} onOpenChange={setAddOpen}>
                <PopoverTrigger asChild>
                  <button className="flex items-center gap-1 text-xs font-medium text-bull transition-colors hover:text-bull/80">
                    <Plus className="h-3.5 w-3.5" />
                    {t("Add Stock")}
                  </button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-80 p-2">
                  <StockSearchBox
                    mode="add"
                    autoFocus
                    addedSymbols={watchlist.symbols}
                    placeholder={t("Search stocks to add…")}
                    onSelect={(r) => {
                      if (watchlist.symbols.includes(r.symbol)) {
                        toast(`${r.symbol} ${t("is already in your watchlist")}`);
                        return;
                      }
                      watchlist.add(r.symbol);
                      toast.success(`${r.symbol} ${t("added to watchlist")}`);
                    }}
                  />
                </PopoverContent>
              </Popover>
            </div>
            <div className="space-y-1">
              {watchlist.symbols.map((tk) => {
                const fallback = STOCKS[tk];
                const live = snapshot?.find((row) => row.symbol === tk);
                const rawPrice = live?.price ?? fallback?.price ?? null;
                const hasPrice = rawPrice != null && rawPrice > 0;
                const livePrice = rawPrice ?? 0;
                const liveChangePct = live?.change_pct ?? fallback?.changePct ?? 0;
                const liveName =
                  symbolsData?.find((s) => s.symbol === tk)?.name ?? fallback?.name ?? tk;
                const signalForSymbol =
                  batchSignals?.signals?.find((s: { symbol: string }) => s.symbol === tk)?.signal ??
                  fallback?.signal ??
                  "HOLD";
                return (
                  <div
                    key={tk}
                    className="group flex items-center gap-2 rounded-[6px] px-2 py-1.5 hover:bg-hover"
                  >
                    <button
                      onClick={() => {
                        watchlist.remove(tk);
                        toast(`${tk} ${t("removed from watchlist")}`);
                      }}
                      aria-label={`Remove ${tk}`}
                      className="shrink-0"
                    >
                      <Star className="wl-star h-3.5 w-3.5 text-bull" fill="#00d4aa" />
                    </button>
                    <Link
                      to="/stock/$ticker"
                      params={{ ticker: tk }}
                      className="flex flex-1 items-center gap-2"
                    >
                      <div className="flex-1">
                        <div className="wl-symbol text-sm font-semibold text-bull">{tk}</div>
                        <div className="text-[10px] text-text-muted">{t(liveName)}</div>
                      </div>
                      <div className="text-right">
                        {hasPrice ? (
                          <>
                            <div className="font-mono text-sm tabular-nums text-text-primary">
                              {fmtNum(livePrice)}
                            </div>
                            <Change pct={liveChangePct} />
                          </>
                        ) : (
                          <div
                            className="font-mono text-sm tabular-nums text-text-muted"
                            title={t("Live price unavailable")}
                          >
                            —
                          </div>
                        )}
                      </div>
                      <SignalBadge signal={signalForSymbol as Signal} />
                    </Link>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card>
            <div className="mb-2 flex gap-1">
              {(["Gainers", "Losers", "Most Active"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setMoverTab(tab)}
                  className={cn(
                    "rounded-[6px] px-2.5 py-1 text-xs font-medium",
                    moverTab === tab
                      ? "bg-bull/15 text-bull"
                      : "text-text-secondary hover:bg-hover",
                  )}
                >
                  {t(tab)}
                </button>
              ))}
            </div>
            <table className="w-full text-xs">
              <tbody>
                {movers.map((s, i) => (
                  <tr key={s.ticker} className={cn(i % 2 ? "bg-surface-alt" : "bg-surface")}>
                    <td className="py-1.5 pl-2 text-text-muted">{i + 1}</td>
                    <td className="font-semibold text-text-primary">{s.ticker}</td>
                    <td className="text-right font-mono tabular-nums text-text-primary">
                      {fmtNum(s.price)}
                    </td>
                    <td className="px-2 text-right">
                      <Change pct={s.changePct} />
                    </td>
                    <td className="pr-2 text-right font-mono tabular-nums text-text-muted">
                      {s.volume}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

        </div>
      </div>

      {/* Full-width Sector Heatmap */}
      <Card className="mt-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-text-primary">
              {drilledSector ? t(drilledSector) : t("Sector Heatmap")}
            </h3>
            <p className="text-[11px] text-text-muted">
              {treemapData
                ? `${treemapData.sectors.length} ${t("sectors")} · ${treemapData.stock_count} ${t("stocks")}`
                : t("Loading…")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Sort dropdown */}
            <select
              value={heatmapSort}
              onChange={(e) => setHeatmapSort(e.target.value as "cap" | "change" | "volume")}
              className="rounded-[6px] border border-border bg-surface px-2 py-1 text-xs text-text-primary"
              disabled={!!drilledSector}
            >
              <option value="cap">{t("By Market Cap")}</option>
              <option value="change">{t("By % Change")}</option>
              <option value="volume">{t("By Volume")}</option>
            </select>
            {/* View toggle */}
            <div className="flex items-center gap-0.5 rounded-[6px] border border-border bg-surface p-0.5">
              <button
                type="button"
                onClick={() => setHeatmapView("treemap")}
                className={cn(
                  "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-xs font-medium transition",
                  heatmapView === "treemap"
                    ? "bg-bull text-bull-foreground"
                    : "text-text-secondary hover:bg-hover"
                )}
                title={t("Treemap view")}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setHeatmapView("sectors")}
                className={cn(
                  "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-xs font-medium transition",
                  heatmapView === "sectors"
                    ? "bg-bull text-bull-foreground"
                    : "text-text-secondary hover:bg-hover"
                )}
                title={t("Sectors bar list")}
              >
                <List className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setHeatmapView("movers")}
                className={cn(
                  "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-xs font-medium transition",
                  heatmapView === "movers"
                    ? "bg-bull text-bull-foreground"
                    : "text-text-secondary hover:bg-hover"
                )}
                title={t("Top Movers")}
              >
                <Flame className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>

        {treemapData && (
          <HeatmapLegend asOf={treemapData.as_of} />
        )}

        <div className="mt-3">
          {heatmapView === "treemap" ? (
            isLoadingTreemap ? (
              <HeatmapSkeleton height={560} />
            ) : sortedTreemapData && sortedTreemapData.sectors.length > 0 ? (
              <Treemap
                data={sortedTreemapData}
                height={560}
                drilledSector={drilledSector}
                onStockClick={(sym) => navigate({ to: "/stock/$ticker", params: { ticker: sym } })}
                onSectorClick={(sectorName) => setDrilledSector(sectorName)}
                onDrillUp={() => setDrilledSector(null)}
              />
            ) : (
              <HeatmapEmptyState height={560} />
            )
          ) : heatmapView === "sectors" ? (
            <div className="space-y-1">
              {sortedTreemapData?.sectors.map((s) => (
                <button
                  key={s.name}
                  type="button"
                  onClick={() => {
                    setHeatmapView("treemap");
                    setDrilledSector(s.name);
                  }}
                  className="flex w-full items-center gap-2 rounded-[4px] px-2 py-1.5 text-xs hover:bg-hover"
                >
                  <span className="w-40 truncate text-left font-medium text-text-primary">
                    {t(s.name)}
                  </span>
                  <span className="text-text-muted">· {s.stock_count}</span>
                  <div className="flex-1">
                    <div className="h-4 overflow-hidden rounded bg-surface-alt">
                      <div
                        className="h-full rounded transition-all"
                        style={{
                          width: `${Math.min(Math.abs(s.avg_change_pct) * 5, 100)}%`,
                          backgroundColor:
                            (s.avg_change_pct ?? 0) >= 0
                              ? "var(--color-bull)"
                              : "var(--color-bear)",
                        }}
                      />
                    </div>
                  </div>
                  <Change pct={s.avg_change_pct ?? 0} />
                </button>
              ))}
            </div>
          ) : (
            sortedTreemapData ? (
              <TopMoversView data={sortedTreemapData} />
            ) : (
              <HeatmapSkeleton height={560} />
            )
          )}
        </div>
      </Card>
    </div>
  );
}
