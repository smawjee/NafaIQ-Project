import { useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CandlestickChart as CandleIcon } from "lucide-react";

import { Card } from "@/components/shared/Card";
import { MarketBriefCard } from "@/features/psx/components/MarketBriefCard";
import { Change } from "@/components/market/Change";
import { CandlestickChart, PriceLineChart } from "@/components/charts/charts";
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
import { useLang } from "@/hooks/use-lang";
import { MarketTicker } from "@/features/psx/components/MarketTicker";
import { type TopMover } from "@/features/heatmap/TopMoversView";
import { PsxIndexOverview } from "@/features/psx/components/PsxIndexOverview";
import { PsxScreenerCard } from "@/features/psx/components/PsxScreenerCard";
import { PsxWatchlistCard } from "@/features/psx/components/PsxWatchlistCard";
import { PsxMoversCard } from "@/features/psx/components/PsxMoversCard";
import { PsxSectorHeatmap } from "@/features/psx/components/PsxSectorHeatmap";
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
  const [heatmapSort, setHeatmapSort] = useState<"size" | "change" | "volume">("size");
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
      // Real OHLCV, oldest -> newest. Do NOT cap here: `full` is the whole
      // fetched series and `data` below slices it to the selected timeframe.
      // A .slice(-250) here silently pinned "All" (tfDays = 3650) to 250 bars,
      // defeating the deep-history paging all the way from get_history.
      return asc(ohlcvData);
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

  // Unique sector names for the screener filter dropdown.
  const sectorOptions = useMemo(() => {
    const uniq = new Set<string>();
    if (symbolsData) {
      for (const s of symbolsData) {
        if (s.sector) uniq.add(s.sector);
      }
    }
    return Array.from(uniq).sort();
  }, [symbolsData]);

  const sortedTreemapData = useMemo(() => {
    if (!treemapData) return null;
    // The backend already orders sectors by total_size_metric — a real market
    // cap for most stocks, a volume proxy for the rest. Not a pure cap sort.
    if (heatmapSort === "size") return treemapData;

    // Sectors carry no total_volume, so derive it from their stocks.
    const sectorVolume = (s: typeof treemapData.sectors[0]) =>
      s.stocks.reduce((sum, st) => sum + (st.volume ?? 0), 0);

    const sortKey = heatmapSort === "change"
      ? (a: typeof treemapData.sectors[0], b: typeof treemapData.sectors[0]) => Math.abs(b.avg_change_pct) - Math.abs(a.avg_change_pct)
      : (a: typeof treemapData.sectors[0], b: typeof treemapData.sectors[0]) => sectorVolume(b) - sectorVolume(a);

    return {
      ...treemapData,
      sectors: [...treemapData.sectors].sort(sortKey),
    };
  }, [treemapData, heatmapSort]);

  // The payload's top-level stock_count is pre-cap, but each sector only ships
  // its 20 largest stocks — so summing the per-sector counts is the only figure
  // that matches the tiles actually on screen.
  const renderedStockCount = useMemo(
    () => (treemapData?.sectors ?? []).reduce((n, s) => n + s.stock_count, 0),
    [treemapData],
  );

  // Top Movers spans the whole market, so it reads the uncapped snapshot rather
  // than the treemap payload — a small-cap limit-up never survives the backend's
  // per-sector cap. "abs" ranks by |change| so fallers appear too; "gainers"
  // filters to changePct > 0 and could only ever show half the movers.
  const allMovers = useMarketMovers("abs", 30);
  const topMovers = useMemo<TopMover[]>(
    () =>
      allMovers
        .map((m) => ({
          symbol: m.symbol,
          sector: m.sector,
          price: m.price,
          change_pct: m.changePct,
          volume: m.volume,
          market_cap: metricsMap.get(m.symbol)?.market_cap ?? null,
        })),
    [allMovers, metricsMap],
  );

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
      <PsxIndexOverview
        indices={displayIndices}
        showAll={showAllIndices}
        canToggle={indexCardsAll.length > 4}
        onToggleShowAll={() => setShowAllIndices((v) => !v)}
      />

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

          {/* AI market brief — verified pipeline, no fabricated signal/confidence */}
          <MarketBriefCard />

          <PsxScreenerCard
            rows={visibleScreened}
            screenedCount={screened.length}
            screenerStart={screenerStart}
            screenerEnd={screenerEnd}
            currentPage={currentScreenerPage}
            pageCount={screenerPageCount}
            onPrev={() => setScreenerPage((p) => Math.max(1, p - 1))}
            onNext={() => setScreenerPage((p) => Math.min(screenerPageCount, p + 1))}
            searchFilter={searchFilter}
            onSearchChange={setSearchFilter}
            sectorFilter={sectorFilter}
            onSectorChange={setSectorFilter}
            sectors={sectorOptions}
            signalFilter={signalFilter}
            onSignalChange={setSignalFilter}
          />
        </div>

        {/* Right panel */}
        <div className="min-w-0 space-y-4">
          <PsxWatchlistCard
            symbols={watchlist.symbols}
            onAdd={watchlist.add}
            onRemove={watchlist.remove}
            addOpen={addOpen}
            onAddOpenChange={setAddOpen}
            snapshot={snapshot}
            symbolsData={symbolsData}
            batchSignals={batchSignals}
          />

          <PsxMoversCard moverTab={moverTab} onMoverTabChange={setMoverTab} movers={movers} />
        </div>
      </div>

      {/* Full-width Sector Heatmap */}
      <PsxSectorHeatmap
        treemapData={treemapData}
        sortedTreemapData={sortedTreemapData}
        isLoadingTreemap={isLoadingTreemap}
        heatmapView={heatmapView}
        onHeatmapView={setHeatmapView}
        heatmapSort={heatmapSort}
        onHeatmapSort={setHeatmapSort}
        drilledSector={drilledSector}
        onDrillSector={setDrilledSector}
        onDrillUp={() => setDrilledSector(null)}
        renderedStockCount={renderedStockCount}
        topMovers={topMovers}
        onStockNavigate={(sym) => navigate({ to: "/stock/$ticker", params: { ticker: sym } })}
      />
    </div>
  );
}
