import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  Sparkles,
  Plus,
  Star,
  Filter,
  CandlestickChart as CandleIcon,
  LineChart as LineIcon,
} from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { toast } from "sonner";

import { Card } from "@/components/shared/Card";
import { InfoTip } from "@/components/shared/InfoTip";
import { CountUpNumber } from "@/components/charts/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { Change } from "@/components/charts/Change";
import { SignalBadge } from "@/components/charts/SignalBadge";
import { CandlestickChart, PriceLineChart, Sparkline } from "@/components/charts/charts";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";
import {
  INDICES,
  STOCKS,
  STOCK_LIST,
  SECTORS,
  generateOHLCV,
  sma,
  fmtNum,
  type Signal,
  type Candle,
} from "@/lib/data";
import {
  usePsxLiveMarket,
  usePsxRealtime,
  usePsxHistory,
  usePsxSectors,
  usePsxSymbols,
  usePsxIndexData,
  usePsxBatchSignals,
  usePsxScreenerMetrics,
  useMarketTickers,
  useMarketMovers,
  useIndexCards,
} from "@/hooks/psx/use-psx";
import { formatNumber, formatCompactPKR } from "@/lib/format";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { useDemo } from "@/hooks/use-demo";
import { StatsGridSkeleton, ChartSkeleton, TableSkeleton } from "@/components/shared/PageSkeleton";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export const Route = createFileRoute("/psx")({
  head: () => ({
    meta: [
      { title: "PSX Market — NafaIQ Trading Terminal" },
      {
        name: "description",
        content:
          "Live KSE-100 candlestick terminal, top movers, sector heatmap and AI stock screener.",
      },
    ],
  }),
  component: PSX,
});

const SYMBOLS = ["KSE-100", ...Object.keys(STOCKS)];
const TIMEFRAMES = ["1D", "1W", "1M", "3M", "6M", "1Y", "All"] as const;
const INDICATORS = ["MA20", "MA50", "MA100", "MA200"] as const;

// Short definitions for the benchmark-index cards, keyed by display name.
const INDEX_INFO: Record<string, string> = {
  "KSE-100": "Benchmark index tracking the top listed companies on PSX.",
  "KSE-30": "Index of 30 highly liquid companies on the Pakistan Stock Exchange.",
  "KMI-30": "Shariah-compliant index of 30 selected PSX companies.",
  "KSE All Share": "Broad market index covering listed PSX shares.",
};

function tfDays(tf: string) {
  return { "1D": 5, "1W": 14, "1M": 30, "3M": 90, "6M": 130, "1Y": 250, All: 250 }[tf] ?? 250;
}

function symbolMeta(sym: string) {
  if (sym === "KSE-100") return { seed: 1, start: 65000, end: 78542.1, vMin: 200, vMax: 800 };
  const s = STOCKS[sym];
  return { seed: s.seed, start: s.start, end: s.price, vMin: 100, vMax: 600 };
}

function MarketTicker() {
  const { t } = useLang();
  const { isDemo } = useDemo();
  const tickers = useMarketTickers(20);
  // Real users never see fabricated tickers: fall back to the static list only
  // in demo mode, otherwise render nothing until live data arrives.
  const rows = tickers.length
    ? tickers
    : isDemo
      ? STOCK_LIST.map((s) => ({
          symbol: s.ticker,
          name: s.name,
          sector: s.sector,
          price: s.price,
          change: 0,
          changePct: s.changePct,
          volume: 0,
        }))
      : [];
  const row = [...rows, ...rows];
  return (
    <div className="market-strip overflow-hidden rounded-[10px]">
      <div className="flex items-stretch">
        <div className="market-strip flex shrink-0 items-center gap-1.5 rounded-none border-y-0 border-l-0 px-3 text-[11px] font-semibold uppercase tracking-wide">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-bull" />
          <span className="text-bull">{t("Live")}</span>
        </div>
        <div className="flex-1 overflow-hidden py-2">
          <div className="flex w-max animate-ticker gap-6 pl-6">
            {row.map((s, i) => (
              <span key={i} className="flex items-center gap-2 whitespace-nowrap text-[12px]">
                <span className="font-semibold text-text-primary">{s.symbol}</span>
                <span className="font-mono tabular-nums market-strip-muted">{fmtNum(s.price)}</span>
                <span
                  className={cn(
                    "font-mono tabular-nums",
                    s.changePct >= 0 ? "text-bull" : "text-bear",
                  )}
                >
                  {s.changePct >= 0 ? "+" : ""}
                  {s.changePct.toFixed(2)}%
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PSX() {
  const { t } = useLang();
  const [sym, setSym] = useState("KSE-100");
  const [tf, setTf] = useState<string>("6M");
  const [type, setType] = useState<"candle" | "line">("candle");
  const [mas, setMas] = useState<string[]>(["MA20", "MA50", "MA100"]);
  const [moverTab, setMoverTab] = useState<"Gainers" | "Losers" | "Most Active">("Gainers");
  const [signalFilter, setSignalFilter] = useState<string>("All");
  const [sectorFilter, setSectorFilter] = useState<string>("All");
  const [searchFilter, setSearchFilter] = useState("");
  const [screenerPage, setScreenerPage] = useState(1);
  const [showAllSectors, setShowAllSectors] = useState(false);
  const watchlist = useWatchlist();
  const { isDemo } = useDemo();
  const [addOpen, setAddOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const { data: snapshot } = usePsxLiveMarket();
  usePsxRealtime();
  const { data: ohlcvData } = usePsxHistory(sym === "KSE-100" ? "KSE100" : sym);
  const { data: sectorData } = usePsxSectors();
  const { data: symbolsData } = usePsxSymbols();
  const { data: kse100Data } = usePsxIndexData("KSE100");
  const { data: batchSignals } = usePsxBatchSignals(50);
  const { data: screenerMetrics } = usePsxScreenerMetrics();
  const marketMovers = useMarketMovers(
    moverTab === "Gainers" ? "gainers" : moverTab === "Losers" ? "losers" : "volume",
    6,
  );
  const indexCards = useIndexCards();

  const displayIndices = useMemo(() => {
    if (indexCards.length > 0) {
      return indexCards.map((ic) => ({
        key: ic.name,
        name: ic.name,
        value: ic.value,
        change: ic.change,
        changePct: ic.changePct,
        spark: new Array(7).fill(ic.value),
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
  }, [indexCards]);

  useEffect(() => {
    const id = setTimeout(() => setLoading(false), 300);
    return () => clearTimeout(id);
  }, []);

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

  const sectorRows = useMemo(() => {
    if (sectorData && sectorData.length > 0) {
      return sectorData.map((s) => ({
        name: s.name,
        pct: s.pct,
        volume: s.volume ?? 0,
      }));
    }
    // Real users never see fabricated sectors — only demo falls back.
    if (!isDemo) return [];
    return SECTORS.map((s) => ({ name: s.name, pct: s.pct, volume: 0 }));
  }, [sectorData, isDemo]);
  const heatmapRows = showAllSectors ? sectorRows : sectorRows.slice(0, 12);

  useEffect(() => {
    setScreenerPage(1);
  }, [searchFilter, sectorFilter, signalFilter]);

  if (loading) {
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
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
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

      <div className="grid min-w-0 gap-6 lg:grid-cols-[65fr_35fr]">
        {/* Chart column */}
        <div className="min-w-0 space-y-4">
          <Card hover={false} className="bg-surface-alt p-3">
            {/* Toolbar */}
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <select
                value={sym}
                onChange={(e) => setSym(e.target.value)}
                className="min-w-0 max-w-[180px] flex-1 truncate rounded-[6px] border border-border bg-elevated px-2.5 py-1.5 text-sm font-medium text-text-primary sm:flex-none"
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>
                    {s === "KSE-100" ? t("KSE-100 Index") : `${s} · ${t(STOCKS[s].name)}`}
                  </option>
                ))}
              </select>
              <div className="flex flex-wrap gap-1">
                {TIMEFRAMES.map((t) => (
                  <button
                    key={t}
                    onClick={() => setTf(t)}
                    className={cn(
                      "rounded-[6px] px-2 py-1 text-xs font-medium",
                      tf === t
                        ? "tf-active bg-bull text-bull-foreground"
                        : "text-text-secondary hover:bg-hover",
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1 sm:ml-auto">
                <button
                  onClick={() => setType("candle")}
                  className={cn(
                    "rounded-[6px] p-1.5",
                    type === "candle"
                      ? "bg-bull/15 text-bull"
                      : "text-text-secondary hover:bg-hover",
                  )}
                >
                  <CandleIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setType("line")}
                  className={cn(
                    "rounded-[6px] p-1.5",
                    type === "line" ? "bg-bull/15 text-bull" : "text-text-secondary hover:bg-hover",
                  )}
                >
                  <LineIcon className="h-4 w-4" />
                </button>
                {INDICATORS.map((m) => (
                  <button
                    key={m}
                    onClick={() =>
                      setMas((p) => (p.includes(m) ? p.filter((x) => x !== m) : [...p, m]))
                    }
                    className={cn(
                      "rounded-[6px] px-2 py-1 text-[10px] font-medium",
                      mas.includes(m) ? "bg-info/20 text-info" : "text-text-muted hover:bg-hover",
                    )}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>

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
                  {type === "line" ? (
                    <PriceLineChart data={data} height={9999} mas={mas} maSeries={maSeries} />
                  ) : (
                    <CandlestickChart data={data} height={9999} mas={mas} maSeries={maSeries} />
                  )}
                </div>
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

          <Card>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">{t("Sector Heatmap")}</h3>
                <p className="text-[11px] text-text-muted">
                  {showAllSectors
                    ? `${t("Showing all sectors")} (${sectorRows.length})`
                    : `${t("Top sectors")} (${Math.min(heatmapRows.length, sectorRows.length)} ${t("of")} ${sectorRows.length})`}
                </p>
              </div>
              {sectorRows.length > 12 && (
                <button
                  type="button"
                  onClick={() => setShowAllSectors((v) => !v)}
                  className="shrink-0 rounded-[6px] border border-border px-2 py-1 text-xs font-medium text-text-secondary hover:bg-hover hover:text-text-primary"
                >
                  {showAllSectors ? t("Show less") : t("Show all")}
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {heatmapRows.map((s) => {
                const up = s.pct >= 0;
                const intensity = Math.min(Math.abs(s.pct) / 2.6, 1);
                const bg = up
                  ? `rgba(0,212,170,${0.15 + intensity * 0.55})`
                  : `rgba(229,72,77,${0.15 + intensity * 0.55})`;
                return (
                  <div
                    key={s.name}
                    className="flex min-h-[76px] flex-col justify-between rounded-[8px] border border-white/[0.04] p-2.5"
                    style={{ background: bg }}
                    title={`${s.name}: ${up ? "+" : ""}${s.pct.toFixed(1)}%`}
                  >
                    <div className="line-clamp-2 text-[11px] font-semibold leading-snug text-text-primary/90">
                      {t(s.name)}
                    </div>
                    <div className="font-mono text-lg font-bold tabular-nums text-text-primary">
                      {up ? "+" : ""}
                      {s.pct.toFixed(1)}%
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
