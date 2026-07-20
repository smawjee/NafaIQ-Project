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
  usePsxSignalV2,
  usePsxSymbols,
  usePsxRealtime,
} from "@/hooks/psx/use-psx";
import { SignalBreakdownPanel } from "@/features/signals/SignalBreakdownPanel";
import type { SignalHorizon } from "@/lib/psx/types";
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
import { reconcileLiveCandle, tfDays, type LiveCandleInput } from "@/features/psx/psx.utils";

export function StockDetail() {
  const { ticker } = useParams({ from: "/stock/$ticker" });
  const { t } = useLang();
  const navigate = useNavigate();
  const { isDemo } = useDemo();
  const upper = ticker.toUpperCase();
  const s = STOCKS[ticker];

  // Phase 0 / B5: per-symbol timeframe persistence
  const { tfFor, setTfFor } = usePersistedTfMap("6M");
  const { data: quote } = usePsxQuote(ticker);
  // Key off `upper` to match the toolbar's tfFor/setTfFor calls below —
  // a lowercase URL (/stock/hbl) would otherwise read a different tf entry.
  const { data: ohlcvData } = usePsxHistory(ticker, Math.max(365, tfDays(tfFor(upper))));
  const { data: profile } = usePsxProfile(ticker);
  const { data: fundamentals } = usePsxFundamentals(ticker);
  const { data: announcements } = usePsxAnnouncements(ticker, 5);
  const { data: signal } = usePsxSignal(ticker);
  const [signalHorizon, setSignalHorizon] = useState<SignalHorizon>("20D");
  const { data: signalV2 } = usePsxSignalV2(ticker, signalHorizon);
  const { data: symbolsData } = usePsxSymbols();
  const wl = useWatchlist();

  const [chartType, setChartType] = useState<"candle" | "line">("candle");
  const [chartMas, setChartMas] = useState<Indicator[]>(["MA20", "MA50", "MA100"]);
  const tf = tfFor(upper) as Timeframe;
  const setTf = (next: Timeframe) => setTfFor(upper, next);

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

  // Signal: only trust the model when it is trained. Demo mode shows the
  // curated showcase signal; otherwise a pending model shows no fake call.
  const modelReady = !!signalV2 || (!!signal && signal.model_version !== "fallback");
  const sig =
    signalV2?.signal ??
    (modelReady ? (signal?.signal ?? null) : isDemo ? (s?.signal ?? null) : null);
  const confidence = signalV2?.confidence ?? signal?.confidence ?? 0;
  const signalPending = !modelReady && !isDemo;

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
  const data = useMemo(() => {
    const visibleCount = tfDays(tf);
    return chartHistory.slice(-visibleCount);
  }, [chartHistory, tf]);
  const maSeries = useMemo(() => {
    const visibleCount = tfDays(tf);
    const start = Math.max(0, chartHistory.length - visibleCount);
    return {
      ma20: sma(chartHistory, 20).slice(start),
      ma50: sma(chartHistory, 50).slice(start),
      ma100: sma(chartHistory, 100).slice(start),
      ma200: sma(chartHistory, 200).slice(start),
    };
  }, [chartHistory, tf]);
  const lastBar = data[data.length - 1];
  const isLive = quote?.price != null && quote.price > 0;

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
        className="inline-flex items-center gap-1.5 rounded-[8px] border border-white/[0.08] bg-surface px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:border-white/[0.16] hover:text-text-primary"
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
        confidence={confidence}
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

      <SignalBreakdownPanel
        signal={signalV2}
        horizon={signalHorizon}
        onHorizonChange={setSignalHorizon}
      />

      <StockTabs tab={tab} onTabChange={setTab} announcements={announcements} symbol={upper} />

      {/* Desktop action bar */}
      <Card hover={false} className="hidden lg:block">
        <div className="flex flex-wrap items-center gap-2">
          <ActionButtons
            isInWatchlist={isInWatchlist}
            wlBusy={wlBusy}
            onToggleWatchlist={toggleWatchlist}
            onAddPortfolio={() => navigate({ to: "/portfolio" })}
            onSetAlert={openAlert}
            t={t}
          />
        </div>
      </Card>

      {/* Mobile sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/[0.08] bg-surface/95 p-3 backdrop-blur lg:hidden">
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
