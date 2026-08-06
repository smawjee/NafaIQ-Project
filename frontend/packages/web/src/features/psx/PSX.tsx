import { useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CandlestickChart as CandleIcon } from "lucide-react";

import { Card } from "@/components/shared/Card";
import { MarketBriefCard } from "@/features/psx/components/MarketBriefCard";
import { Change } from "@/components/market/Change";
import { CandlestickChart, PriceLineChart } from "@/components/charts/charts";
import { ChartToolbar, type Indicator, type Timeframe } from "@/components/charts/ChartToolbar";
import {
  INDICES,
  STOCKS,
  STOCK_LIST,
  generateOHLCV,
  sma,
  fmtNum,
  type Candle,
  type Signal,
} from "@/lib/data";
import {
  usePsxLiveMarket,
  usePsxRealtime,
  usePsxHistory,
  usePsxIntraday,
  usePsxSymbols,
  usePsxIndexData,
  usePsxBatchSignals,
  usePsxScreenerMetrics,
  usePsxTreemap,
  useMarketMovers,
  useIndexCards,
  indexNameToCode,
} from "@/hooks/psx/use-psx";
import { usePersistedTfMap } from "@/hooks/psx/use-persisted-tf-map";
import { formatNumber, formatCompact, formatCompactPKR } from "@/lib/format";
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
import {
  fetchDaysFor,
  indexBarsHaveNoRange,
  intradayFallbackBars,
  reconcileLiveCandle,
  symbolMeta,
  tfSpec,
  windowBars,
  windowStartIndex,
  type LiveCandleInput,
} from "@/features/psx/psx.utils";

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
  const [showAllIndices, setShowAllIndices] = useState(true);
  const [heatmapView, setHeatmapView] = useState<"treemap" | "sectors" | "movers">("treemap");
  const [drilledSector, setDrilledSector] = useState<string | null>(null);
  const [heatmapSort, setHeatmapSort] = useState<"size" | "change" | "volume">("size");
  const watchlist = useWatchlist();
  const { isDemo } = useDemo();
  const [addOpen, setAddOpen] = useState(false);
  const { data: snapshot, isLoading: snapshotLoading } = usePsxLiveMarket();
  const selectedIndexCode = indexNameToCode(sym);
  const selectedStockSymbol = selectedIndexCode ? undefined : sym.toUpperCase();
  const realtimeSymbols = useMemo(
    () =>
      Array.from(
        new Set([...watchlist.symbols, ...(selectedStockSymbol ? [selectedStockSymbol] : [])]),
      ),
    [selectedStockSymbol, watchlist.symbols],
  );
  // Scope realtime to this user's watchlist plus the active stock chart symbol,
  // so the chart/header and watchlist refresh from the same live tick.
  usePsxRealtime(realtimeSymbols);
  const spec = tfSpec(tf);
  // One fetch depth covers 1D…1Y, so the toolbar re-slices cached bars instead
  // of firing a request per button; only "All" pays for the full history.
  const { data: ohlcvData } = usePsxHistory(selectedIndexCode ? undefined : sym, fetchDaysFor(tf));
  // Intraday exists for equities only — `psx_intraday` is fed from
  // `psx_market_snapshot`, which carries no index rows. An index on 1D/1W
  // therefore falls through to the daily fallback below.
  const { data: intradayData } = usePsxIntraday(
    selectedIndexCode ? undefined : sym,
    spec.sessions || 1,
    spec.kind === "intraday" && !selectedIndexCode,
  );
  const { data: symbolsData } = usePsxSymbols();
  const { data: selectedIndexData } = usePsxIndexData(selectedIndexCode);
  const { data: kse100Data } = usePsxIndexData("KSE100");
  const { data: batchSignals } = usePsxBatchSignals(50);
  const { data: screenerMetrics } = usePsxScreenerMetrics();
  const { data: treemapData, isLoading: isLoadingTreemap } = usePsxTreemap();
  const marketMovers = useMarketMovers(
    moverTab === "Gainers" ? "gainers" : moverTab === "Losers" ? "losers" : "volume",
    6,
  );
  const indexCardsAll = useIndexCards(18);
  const indexCards = indexCardsAll;
  const selectedIndexCard = selectedIndexCode
    ? indexCards.find((card) => card.code === selectedIndexCode)
    : undefined;
  const selectedStockQuote = selectedStockSymbol
    ? snapshot?.find((row) => row.symbol === selectedStockSymbol)
    : undefined;
  const chartLiveCandle = useMemo<LiveCandleInput | null>(() => {
    if (selectedIndexCard) {
      return {
        price: selectedIndexCard.value,
        change: selectedIndexCard.change,
        changePct: selectedIndexCard.changePct,
        date: selectedIndexCard.date,
      };
    }
    if (selectedStockQuote) {
      return {
        price: selectedStockQuote.price,
        change: selectedStockQuote.change,
        changePct: selectedStockQuote.change_pct,
        dayHigh: selectedStockQuote.day_high,
        dayLow: selectedStockQuote.day_low,
        volume: selectedStockQuote.volume,
      };
    }
    return null;
  }, [selectedIndexCard, selectedStockQuote]);

  const getSparkline = useCallback(
    (ic: { name: string; value: number; change: number; changePct: number }, index: number) => {
      if (ic.name === "KSE-100" && kse100Data && kse100Data.length >= 7) {
        return kse100Data.slice(-7).map((d) => d.close);
      }
      // Generate a plausible 7-day trend based on current value and daily change
      const step = ic.change / 6 || 0;
      return Array.from({ length: 7 }, (_, i) => ic.value - step * (6 - i));
    },
    [kse100Data],
  );

  const displayIndices = useMemo(() => {
    if (indexCards.length > 0) {
      return indexCards.map((ic, i) => ({
        key: ic.name,
        code: ic.code,
        name: ic.name,
        value: ic.value,
        change: ic.change,
        changePct: ic.changePct,
        date: ic.date,
        spark: getSparkline(ic, i),
      }));
    }
    return INDICES.map((idx) => ({
      key: idx.name,
      code: indexNameToCode(idx.name) ?? idx.name,
      name: idx.name,
      value: idx.value,
      change: idx.change,
      changePct: idx.changePct,
      date: null,
      spark: generateOHLCV(idx.seed, idx.start, idx.end, 7).map((c) => c.close),
    }));
  }, [indexCards, getSparkline]);

  const full = useMemo(() => {
    const asc = <T extends { date: string }>(rows: T[]) =>
      [...rows].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    let historical: Candle[] = [];
    // Indices live in psx_index_eod/live index endpoints, never psx_ohlcv.
    if (selectedIndexCode) {
      if (selectedIndexData && selectedIndexData.length > 0) {
        historical = asc(selectedIndexData).map((b) => ({
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
      historical = asc(ohlcvData);
    }
    if (historical.length > 0) return reconcileLiveCandle(historical, chartLiveCandle);
    // Demo users see realistic generated candles; real users never see dummy data
    // (an empty array renders a clean "no data" state below).
    if (isDemo) {
      const meta = symbolMeta(sym);
      return reconcileLiveCandle(
        generateOHLCV(meta.seed, meta.start, meta.end, 250, meta.vMin, meta.vMax),
        chartLiveCandle,
      );
    }
    return [];
  }, [selectedIndexCode, selectedIndexData, sym, ohlcvData, chartLiveCandle, isDemo]);

  // Phase 0 / B3: index EOD rows carry no intraday range, so a candlestick has
  // nothing to draw — fall back to a line chart and show a real curve.
  //
  // This used to test only for NULL open/high/low. The API never returns nulls:
  // it coalesces the missing columns to the close, so every KSE-100 bar arrives
  // as open == high == low == close. The guard therefore never fired and the
  // index chart rendered 1,000 zero-range dojis — a row of 1px dashes. Testing
  // for "no range" catches both shapes, and a genuine OHLC index (any bar with
  // a high above its low) still draws as candles.
  const indexHasNoCandleRange = useMemo(() => {
    if (!selectedIndexCode) return false;
    return indexBarsHaveNoRange(selectedIndexData ?? []);
  }, [selectedIndexCode, selectedIndexData]);
  const effectiveType = indexHasNoCandleRange ? "line" : type;

  // 1D/1W draw 5-minute bars when there are any. Indices never have them, and
  // equities won't before the market has been open with the capture job
  // running, so both fall back to a short window of daily candles.
  const hasIntraday = spec.kind === "intraday" && (intradayData?.length ?? 0) > 0;
  const data = useMemo(() => {
    if (hasIntraday) return windowBars(intradayData!, tf);
    if (spec.kind === "intraday") return full.slice(-intradayFallbackBars(tf));
    // The window is measured in calendar time from the newest bar, not in
    // bars: `slice(-tfDays(tf))` treated a calendar-day count as a bar count
    // and over-rendered every timeframe by ~1.45x.
    return windowBars(full, tf);
  }, [full, hasIntraday, intradayData, spec.kind, tf]);
  const hasData = data.length > 0;
  // MAs are computed over the FULL fetched series (so MA200 is warmed up) and
  // sliced with the same start index as the visible bars. Intraday passes
  // `undefined` so the chart derives them from the 5-minute series instead —
  // daily averages plotted against intraday bars would be meaningless.
  const maSeries = useMemo(() => {
    if (spec.kind === "intraday" && hasIntraday) return undefined;
    const start =
      spec.kind === "intraday"
        ? Math.max(0, full.length - intradayFallbackBars(tf))
        : windowStartIndex(full, tf);
    return {
      ma20: sma(full, 20).slice(start),
      ma50: sma(full, 50).slice(start),
      ma100: sma(full, 100).slice(start),
      ma200: sma(full, 200).slice(start),
    };
  }, [full, hasIntraday, spec.kind, tf]);
  const last = data[data.length - 1];
  const livePrice =
    chartLiveCandle?.price != null && Number.isFinite(chartLiveCandle.price)
      ? chartLiveCandle.price
      : null;
  const displayPrice = livePrice ?? last?.close ?? 0;
  const displayChange = chartLiveCandle?.change ?? (hasData ? last.close - last.open : 0);
  const displayChangePct =
    chartLiveCandle?.changePct ?? (hasData && last.open ? (displayChange / last.open) * 100 : 0);

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
      // Signals V4 only: the badge shows the setup label; the legacy v2 detail
      // popover (confidence %, reasons) is retired.
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
          signalDetails: null,
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
        signalDetails: null,
        rsi: metricsMap.get(m.symbol)?.rsi ?? null,
        volume: formatCompact(m.volume ?? 0),
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
    const sectorVolume = (s: (typeof treemapData.sectors)[0]) =>
      s.stocks.reduce((sum, st) => sum + (st.volume ?? 0), 0);

    const sortKey =
      heatmapSort === "change"
        ? (a: (typeof treemapData.sectors)[0], b: (typeof treemapData.sectors)[0]) =>
            Math.abs(b.avg_change_pct) - Math.abs(a.avg_change_pct)
        : (a: (typeof treemapData.sectors)[0], b: (typeof treemapData.sectors)[0]) =>
            sectorVolume(b) - sectorVolume(a);

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
      allMovers.map((m) => ({
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
      <div className="mx-auto w-full max-w-[1680px] space-y-6">
        <MarketTicker />
        <StatsGridSkeleton count={4} />
        <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_400px]">
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
    <div className="mx-auto w-full max-w-[1680px] space-y-6">
      {/* Live market ticker — always-dark dense data strip */}
      <MarketTicker />

      {/* Index overview */}
      <PsxIndexOverview
        indices={displayIndices}
        showAll={showAllIndices}
        canToggle={false}
        onToggleShowAll={() => setShowAllIndices((v) => !v)}
        selectedCode={selectedIndexCode}
        onSelectIndex={(idx) => {
          setSym(idx.name);
        }}
      />

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_400px]">
        {/* Chart column */}
        <div className="min-w-0 space-y-4">
          <Card
            hover={false}
            data-testid="psx-chart-card"
            className="overflow-hidden bg-surface-alt p-3 sm:p-4"
          >
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
                <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="font-mono text-2xl font-bold tabular-nums text-text-primary">
                    {fmtNum(displayPrice)}
                  </span>
                  <Change
                    value={`${displayChange >= 0 ? "+" : ""}${fmtNum(displayChange)}`}
                    pct={displayChangePct}
                  />
                  <span className="font-mono text-xs tabular-nums text-text-muted">
                    O {fmtNum(last.open)} · H {fmtNum(last.high)} · L {fmtNum(last.low)} · Vol{" "}
                    {formatNumber(last.volume, 0)}
                  </span>
                </div>

                <div
                  data-testid="psx-chart-plot"
                  className="h-[340px] min-w-0 overflow-hidden rounded-[10px] border border-border bg-background/35 p-2 md:h-[420px] xl:h-[500px]"
                >
                  {effectiveType === "line" ? (
                    <PriceLineChart
                      key={sym}
                      data={data}
                      height={9999}
                      mas={mas}
                      maSeries={maSeries}
                      currentPrice={!selectedIndexCode ? displayPrice : undefined}
                      tf={tf}
                    />
                  ) : (
                    <CandlestickChart
                      key={sym}
                      data={data}
                      height={9999}
                      mas={mas}
                      maSeries={maSeries}
                      currentPrice={!selectedIndexCode ? displayPrice : undefined}
                      tf={tf}
                    />
                  )}
                </div>
                {/* Say WHY 1D/1W are showing daily candles. Without this the
                    chart silently swaps series and the timeframe button reads
                    as broken. Indices never have intraday bars at all —
                    psx_intraday is fed from the equity snapshot. */}
                {spec.kind === "intraday" && !hasIntraday && (
                  <p className="mt-2 text-[11px] text-text-muted">
                    {selectedIndexCode
                      ? t("Intraday bars aren't available for indices — showing daily candles.")
                      : t(
                          "Intraday bars aren't available for this symbol yet — showing daily candles instead.",
                        )}
                  </p>
                )}
                {indexHasNoCandleRange && selectedIndexCard?.value != null && (
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

      {/* AI market brief â€” verified pipeline, no fabricated signal/confidence */}
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
