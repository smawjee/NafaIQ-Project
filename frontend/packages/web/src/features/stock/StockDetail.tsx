import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { type Indicator, type Timeframe } from "@/components/charts/ChartToolbar";
import { logoUrlFor } from "@/lib/psx/stock-search";
import { STOCKS, sma, type Candle } from "@/lib/data";
import { formatNumber, formatCompactPKR } from "@/lib/format";
import {
  usePsxQuote,
  usePsxHistory,
  usePsxProfile,
  usePsxFundamentals,
  usePsxAnnouncements,
  usePsxSignal,
  usePsxSymbols,
  usePsxRealtime,
  usePsxIntraday,
} from "@/hooks/psx/use-psx";
import { SignalPanel } from "@/features/signals/SignalPanel";
import { usePersistedTfMap } from "@/hooks/psx/use-persisted-tf-map";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { useDemo } from "@/hooks/use-demo";
import { userPost } from "@/lib/psx/client";
import { useLang } from "@/hooks/use-lang";
import { ActionButtons } from "@/features/stock/components/ActionButtons";
import { StockAnalysisReportCard } from "@/features/stock/components/StockAnalysisReportCard";
import { StockDetailHeader } from "@/features/stock/components/StockDetailHeader";
import { StockChartCard } from "@/features/stock/components/StockChartCard";
import { StockTabs, type StockTab } from "@/features/stock/components/StockTabs";
import { PriceAlertModal } from "@/features/stock/components/PriceAlertModal";
import {
  fetchDaysFor,
  intradayFallbackBars,
  reconcileLiveCandle,
  tfSpec,
  windowBars,
  windowStartIndex,
  type LiveCandleInput,
} from "@/features/psx/psx.utils";

export function StockDetail() {
  const { ticker } = useParams({ from: "/stock/$ticker" });
  const { t } = useLang();
  const navigate = useNavigate();
  const { isDemo } = useDemo();
  const upper = ticker.toUpperCase();
  const s = STOCKS[ticker];

  // Phase 0 / B5: per-symbol timeframe persistence
  const { tfFor, setTfFor } = usePersistedTfMap("6M");
  // Key off `upper` to match the toolbar's tfFor/setTfFor calls below —
  // a lowercase URL (/stock/hbl) would otherwise read a different tf entry.
  const tf = tfFor(upper) as Timeframe;
  const setTf = (next: Timeframe) => setTfFor(upper, next);
  const spec = tfSpec(tf);

  const { data: quote } = usePsxQuote(ticker);
  // One fetch depth covers 1D…1Y (see DAILY_FETCH_DAYS), so switching among
  // those timeframes re-slices cached bars instead of re-requesting them.
  const { data: ohlcvData, isLoading: historyLoading } = usePsxHistory(ticker, fetchDaysFor(tf));
  // 5-minute bars, requested only by the intraday timeframes.
  const { data: intradayData, isLoading: intradayLoading } = usePsxIntraday(
    ticker,
    spec.sessions || 1,
    spec.kind === "intraday",
  );
  const { data: profile } = usePsxProfile(ticker);
  const { data: fundamentals } = usePsxFundamentals(ticker);
  const { data: announcements } = usePsxAnnouncements(ticker, 5);
  const { data: signal } = usePsxSignal(ticker);
  const setupRating = signal?.technical_setup?.rating ?? null;
  const setupSignal =
    setupRating === "Strong Bullish"
      ? "STRONG BUY"
      : setupRating === "Bullish"
        ? "BUY"
        : setupRating === "Bearish"
          ? "SELL"
          : setupRating === "Strong Bearish"
            ? "STRONG SELL"
            : setupRating === "Neutral"
              ? "HOLD"
              : null;
  const modelReady = signal?.technical_setup?.status === "available";
  const sig = modelReady ? setupSignal : isDemo ? (s?.signal ?? null) : null;
  const signalPending = !modelReady && !isDemo;
  const { data: symbolsData } = usePsxSymbols();
  const wl = useWatchlist();

  const [chartType, setChartType] = useState<"candle" | "line">("candle");
  const [chartMas, setChartMas] = useState<Indicator[]>(["MA20", "MA50", "MA100"]);

  const [alertOpen, setAlertOpen] = useState(false);
  const [alertCondition, setAlertCondition] = useState<"above" | "below">("above");
  const [alertPrice, setAlertPrice] = useState("");
  const [alertMsg, setAlertMsg] = useState("");
  const [alertSeverity, setAlertSeverity] = useState<"success" | "error" | "info">("info");
  const [alertBusy, setAlertBusy] = useState(false);
  const [wlBusy, setWlBusy] = useState(false);
  const [tab, setTab] = useState<StockTab>("announcements");

  const symbolInfo = symbolsData?.find((x) => x.symbol === upper);

  // Canonical company name: prefer a real name from profile/symbols; never echo
  // the ticker back (avoids "HBL · HBL"). Falls back to the showcase catalog.
  const rawName = profile?.name || symbolInfo?.name || s?.name || "";
  const name = rawName && rawName.toUpperCase() !== upper ? rawName : "";
  const logoUrl = logoUrlFor(symbolInfo?.logoid);

  const price = quote?.price ?? s?.price ?? null;
  const changePct = quote?.change_pct ?? s?.changePct ?? null;
  const change =
    quote?.change ??
    (price != null && changePct != null ? +(price * (changePct / 100)).toFixed(2) : null);
  const sector = profile?.sector ?? s?.sector ?? null;

  // Phase 0 / B4: derive a chart-ready series from the per-stock history
  // and merge the live tick into the latest candle so the chart and headline
  // use the same price source.
  // Phase 0 / B8: subscribe to the realtime channel filtered to this single
  // symbol so small-caps that aren't in the top-20 AHL poll still update
  // in <1s when the user is on their detail page.
  usePsxRealtime([upper]);
  const liveCandle = useMemo<LiveCandleInput | null>(() => {
    if (!quote) return null;
    return {
      price: quote.price,
      change: quote.change,
      changePct: quote.change_pct,
      dayHigh: quote.day_high,
      dayLow: quote.day_low,
      volume: quote.volume,
    };
  }, [quote]);
  const chartHistory = useMemo(
    () => reconcileLiveCandle(((ohlcvData ?? []) as Candle[]).slice(), liveCandle),
    [ohlcvData, liveCandle],
  );
  // An intraday timeframe uses intraday bars when there are any. There won't
  // be on a fresh deployment, for a symbol that has not traded today, or once
  // the retention window has pruned them — so fall back to daily candles and
  // say so, rather than drawing an empty pane.
  const hasIntraday = spec.kind === "intraday" && (intradayData?.length ?? 0) > 0;
  const intradayFallback = spec.kind === "intraday" && !hasIntraday && !intradayLoading;

  const data = useMemo(() => {
    if (hasIntraday) return windowBars(intradayData!, tf);
    if (spec.kind === "intraday") return chartHistory.slice(-intradayFallbackBars(tf));
    return windowBars(chartHistory, tf);
  }, [chartHistory, hasIntraday, intradayData, spec.kind, tf]);

  const maSeries = useMemo(() => {
    // Intraday: let the chart derive MAs from the 5-minute series itself — the
    // daily averages below are on a different time base and would be nonsense
    // plotted against it.
    if (spec.kind === "intraday") return undefined;
    // Daily: the MAs are computed over the FULL fetched history and sliced with
    // the same start index as the visible bars, so MA200 is already warmed up
    // at the window's left edge instead of starting as 200 nulls.
    const start = windowStartIndex(chartHistory, tf);
    return {
      ma20: sma(chartHistory, 20).slice(start),
      ma50: sma(chartHistory, 50).slice(start),
      ma100: sma(chartHistory, 100).slice(start),
      ma200: sma(chartHistory, 200).slice(start),
    };
  }, [chartHistory, spec.kind, tf]);

  const lastBar = data[data.length - 1];
  const isLive = quote?.price != null && quote.price > 0;
  const chartLoading =
    data.length === 0 && (historyLoading || (spec.kind === "intraday" && intradayLoading));

  const marketCap =
    profile?.listed_shares && price ? formatCompactPKR(profile.listed_shares * price) : "—";

  const stats: [string, string][] = [
    ["Market Cap", marketCap],
    ["P/E Ratio", fundamentals?.pe ? fundamentals.pe.toFixed(1) : "—"],
    ["EPS", fundamentals?.eps ? `PKR ${fundamentals.eps.toFixed(2)}` : "—"],
    ["Day High", quote?.day_high ? formatNumber(quote.day_high, 2) : "—"],
    ["Day Low", quote?.day_low ? formatNumber(quote.day_low, 2) : "—"],
    ["Volume", quote?.volume ? formatNumber(quote.volume, 0) : "—"],
    ["Dividend Yield", fundamentals?.div_yield ? `${fundamentals.div_yield.toFixed(1)}%` : "—"],
    ["Sector", sector ? t(sector) : "—"],
  ];

  const isInWatchlist = wl.symbols.includes(upper);

  const toggleWatchlist = async () => {
    if (wlBusy) return;
    setWlBusy(true);
    const wasIn = isInWatchlist;
    try {
      if (wasIn) await wl.remove(ticker);
      else await wl.add(ticker);
      toast.success(wasIn ? t("Removed from Watchlist") : t("Added to Watchlist"));
    } catch {
      toast.error(t("Something went wrong. Please try again."));
    } finally {
      setWlBusy(false);
    }
  };

  const handleSetAlert = async () => {
    const target = parseFloat(alertPrice);
    if (isNaN(target) || target <= 0) {
      setAlertMsg(t("Please enter a valid price"));
      setAlertSeverity("error");
      return;
    }
    setAlertBusy(true);
    try {
      // Route through the backend so plan limits are enforced and duplicate
      // alerts are de-duplicated (the old direct-Supabase upsert bypassed both).
      await userPost("/api/alerts/price", {
        symbol: upper,
        condition: alertCondition,
        price: target,
      });
      toast.success(t("Price alert created"));
      setAlertOpen(false);
      setAlertMsg("");
      setAlertSeverity("success");
    } catch (error) {
      console.error("Set alert error:", error);
      setAlertMsg(t("Could not set alert — you may have reached your plan's alert limit."));
      setAlertSeverity("error");
    } finally {
      setAlertBusy(false);
    }
  };

  const openAlert = () => {
    if (price != null) setAlertPrice(price.toFixed(2));
    setAlertOpen(true);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-24 lg:pb-6">
      <Link
        to="/psx"
        className="inline-flex items-center gap-1.5 rounded-[8px] border border-border bg-surface px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:border-border-hover hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> {t("Back to Market")}
      </Link>

      <StockDetailHeader
        upper={upper}
        name={name}
        sector={sector}
        logoUrl={logoUrl}
        price={price}
        change={change}
        changePct={changePct}
        isLive={isLive}
        sig={sig}
        signalPending={signalPending}
        confidence={null}
      />

      <StockChartCard
        sym={upper}
        tf={tf}
        onTfChange={setTf}
        chartType={chartType}
        onChartTypeChange={setChartType}
        chartMas={chartMas}
        onChartMasChange={setChartMas}
        data={data}
        maSeries={maSeries}
        price={price}
        isLive={isLive}
        lastBar={lastBar}
        isLoading={chartLoading}
        intradayFallback={intradayFallback}
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map(([l, v]) => (
          <Card key={l}>
            <div className="text-xs text-text-muted">{t(l)}</div>
            <div className="mt-1 font-mono text-sm font-bold tabular-nums text-text-primary">
              {v}
            </div>
          </Card>
        ))}
      </div>

      <StockAnalysisReportCard symbol={upper} />

      <SignalPanel signal={signal} />

      <StockTabs tab={tab} onTabChange={setTab} announcements={announcements} symbol={upper} />

      {/* Desktop action bar */}
      <Card hover={false} className="hidden lg:block">
        <div className="grid gap-3 md:grid-cols-3">
          <ActionButtons
            isInWatchlist={isInWatchlist}
            wlBusy={wlBusy}
            onToggleWatchlist={toggleWatchlist}
            onAddPortfolio={() => navigate({ to: "/portfolio" })}
            onSetAlert={openAlert}
            compact
            t={t}
          />
        </div>
      </Card>

      {/* Mobile sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 p-3 backdrop-blur lg:hidden">
        <div className="mx-auto flex max-w-5xl items-center gap-2">
          <ActionButtons
            isInWatchlist={isInWatchlist}
            wlBusy={wlBusy}
            onToggleWatchlist={toggleWatchlist}
            onAddPortfolio={() => navigate({ to: "/portfolio" })}
            onSetAlert={openAlert}
            compact
            t={t}
          />
        </div>
      </div>

      <PriceAlertModal
        open={alertOpen}
        symbol={upper}
        price={price}
        condition={alertCondition}
        onConditionChange={setAlertCondition}
        alertPrice={alertPrice}
        onAlertPriceChange={setAlertPrice}
        msg={alertMsg}
        severity={alertSeverity}
        busy={alertBusy}
        onClose={() => setAlertOpen(false)}
        onSubmit={handleSetAlert}
      />
    </div>
  );
}
