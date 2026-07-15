import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft, X, Loader2, FileText, BarChart3, Newspaper, Banknote } from "lucide-react";
import { ReferenceLine } from "recharts";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { SignalBadge } from "@/components/market/SignalBadge";
import { CandlestickChart, PriceLineChart } from "@/components/charts/charts";
import { ChartToolbar, type Indicator, type Timeframe } from "@/components/charts/ChartToolbar";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { StockLogo } from "@/components/search/StockLogo";
import { logoUrlFor } from "@/lib/psx/stock-search";
import { STOCKS, sma, fmtNum, type Candle } from "@/lib/data";
import { formatNumber, formatSigned, formatSignedPercent, formatCompactPKR } from "@/lib/format";
import {
  usePsxQuote,
  usePsxHistory,
  usePsxProfile,
  usePsxFundamentals,
  usePsxAnnouncements,
  usePsxSignal,
  usePsxSymbols,
  usePsxRealtime,
} from "@/hooks/psx/use-psx";
import { usePersistedTfMap } from "@/hooks/psx/use-persisted-tf-map";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { useDemo } from "@/hooks/use-demo";
import { userPost } from "@/lib/psx/client";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { formatTimeAgo } from "@/features/stock/stock.utils";
import { ActionButtons } from "@/features/stock/components/ActionButtons";
import { StockAnalysisReportCard } from "@/features/stock/components/StockAnalysisReportCard";
import { FilingsTab } from "@/features/stock/FilingsTab";
import { FinancialsTab } from "@/features/stock/FinancialsTab";
import { NewsFeed } from "@/features/psx/NewsFeed";
import { useDividends } from "@/hooks/psx/use-extras";
import { tfDays } from "@/features/psx/psx.utils";

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
  const [tab, setTab] = useState<"announcements" | "filings" | "financials" | "news" | "dividends">("announcements");

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
  const modelReady = !!signal && signal.model_version !== "fallback";
  const sig = modelReady ? signal.signal : isDemo ? (s?.signal ?? null) : null;
  const confidence = signal?.confidence ?? 0;
  const signalPending = !modelReady && !isDemo;

  // Phase 0 / B4: derive a chart-ready series from the per-stock history
  // and slice it by the persisted timeframe. The last bar is yesterday's EOD
  // close; the live `quote.price` is overlaid as a horizontal reference line
  // so the user can see how today's tick sits vs. the recent bars.
  // Phase 0 / B8: subscribe to the realtime channel filtered to this single
  // symbol so small-caps that aren't in the top-20 AHL poll still update
  // in <1s when the user is on their detail page.
  usePsxRealtime([upper]);
  const data = useMemo(() => {
    const full = (ohlcvData ?? []) as Candle[];
    const visibleCount = tfDays(tf);
    return full.slice(-visibleCount);
  }, [ohlcvData, tf]);
  const maSeries = useMemo(() => {
    const full = (ohlcvData ?? []) as Candle[];
    const visibleCount = tfDays(tf);
    const start = Math.max(0, full.length - visibleCount);
    return {
      ma20: sma(full, 20).slice(start),
      ma50: sma(full, 50).slice(start),
      ma100: sma(full, 100).slice(start),
      ma200: sma(full, 200).slice(start),
    };
  }, [ohlcvData, tf]);
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

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-24 lg:pb-6">
      <Link
        to="/psx"
        className="inline-flex items-center gap-1.5 rounded-[8px] border border-white/[0.08] bg-surface px-3 py-1.5 text-sm font-medium text-text-secondary transition-colors hover:border-white/[0.16] hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> {t("Back to Market")}
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <StockLogo symbol={upper} logoUrl={logoUrl} size={44} className="mt-0.5" />
          <div>
            <h1 className="flex flex-wrap items-baseline gap-x-2 text-2xl font-bold text-text-primary">
              <span>{upper}</span>
              {name && <span className="text-lg font-medium text-text-secondary">· {name}</span>}
            </h1>
            <p className="text-sm text-text-secondary">
              {sector ? `${t(sector)} ${t("Sector")}` : t("Pakistan Stock Exchange")}
            </p>
            <div className="mt-2 flex items-baseline gap-3">
              {price != null ? (
                <>
                  <span className="font-mono text-3xl font-bold tabular-nums text-text-primary">
                    <CountUpNumber value={price} decimals={2} prefix="PKR " />
                  </span>
                  {/* Phase 0 / B4: live tick is the "true right-now" price; the
                      chart's last bar is yesterday's EOD close. The badge makes
                      the distinction explicit. */}
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      isLive ? "bg-bull/15 text-bull" : "bg-text-secondary/15 text-text-secondary",
                    )}
                    title={
                      isLive ? t("Live tick from PSX snapshot") : t("EOD close — live unavailable")
                    }
                    aria-label={isLive ? t("Live tick from PSX snapshot") : t("EOD close — live unavailable")}
                  >
                    {isLive ? t("LIVE") : t("EOD")}
                  </span>
                </>
              ) : (
                <span className="font-mono text-3xl font-bold tabular-nums text-text-muted">—</span>
              )}
              {change != null && changePct != null && (
                <span
                  className={cn(
                    "font-mono text-sm font-semibold tabular-nums",
                    change >= 0 ? "text-bull" : "text-bear",
                  )}
                >
                  {formatSigned(change, 2)} ({formatSignedPercent(changePct)})
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right">
          {sig ? (
            <SignalBadge signal={sig} className="text-xs" />
          ) : (
            <span className="inline-flex items-center rounded-full border border-text-secondary/25 bg-text-secondary/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
              {t("Signal unavailable")}
            </span>
          )}
          <div className="mt-1 text-xs text-text-muted">
            {signalPending
              ? t("Model training in progress")
              : sig
                ? `${t("Confidence")} ${confidence}%`
                : ""}
          </div>
        </div>
      </div>

      <Card hover={false} className="bg-surface-alt">
        {/* Phase 0 / B7: stock-detail now uses the same ChartToolbar as /psx */}
        <ChartToolbar
          sym={upper}
          nameFor={() => ""}
          onSymChange={() => {}}
          tf={tf}
          onTfChange={setTf}
          type={chartType}
          onTypeChange={setChartType}
          mas={chartMas}
          onMasChange={setChartMas}
          hideSymbolPicker
        />
        <div className="h-[300px] lg:h-[440px]">
          {data.length > 0 ? (
            chartType === "line" ? (
              <PriceLineChart data={data} height={9999} mas={chartMas} maSeries={maSeries} currentPrice={price} />
            ) : (
              <CandlestickChart data={data} height={9999} mas={chartMas} maSeries={maSeries} currentPrice={price} />
            )
          ) : (
            <div className="flex h-full items-center justify-center text-text-muted text-sm">
              {t("Loading chart data...")}
            </div>
          )}
        </div>
        {data.length > 0 && isLive && lastBar && (
          <p className="mt-2 text-[11px] text-text-muted">
            {t("Dashed line: today's live tick. Bars: EOD history. Last bar close = ")}
            <span className="font-mono">{fmtNum(lastBar.close)}</span>.
          </p>
        )}
      </Card>

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

      <Card>
        <div className="mb-3 flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setTab("announcements")}
            className={cn(
              "rounded-[6px] px-2.5 py-1 text-xs font-semibold transition",
              tab === "announcements"
                ? "bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            {t("Announcements")}
          </button>
          <button
            type="button"
            onClick={() => setTab("filings")}
            className={cn(
              "inline-flex items-center gap-1 rounded-[6px] px-2.5 py-1 text-xs font-semibold transition",
              tab === "filings"
                ? "bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            <FileText className="h-3 w-3" /> {t("Filings")}
          </button>
          <button
            type="button"
            onClick={() => setTab("financials")}
            className={cn(
              "inline-flex items-center gap-1 rounded-[6px] px-2.5 py-1 text-xs font-semibold transition",
              tab === "financials"
                ? "bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            <BarChart3 className="h-3 w-3" /> {t("Financials")}
          </button>
          <button
            type="button"
            onClick={() => setTab("news")}
            className={cn(
              "inline-flex items-center gap-1 rounded-[6px] px-2.5 py-1 text-xs font-semibold transition",
              tab === "news"
                ? "bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            <Newspaper className="h-3 w-3" /> {t("News")}
          </button>
          <button
            type="button"
            onClick={() => setTab("dividends")}
            className={cn(
              "inline-flex items-center gap-1 rounded-[6px] px-2.5 py-1 text-xs font-semibold transition",
              tab === "dividends"
                ? "bg-bull text-bull-foreground"
                : "text-text-secondary hover:bg-hover",
            )}
          >
            <Banknote className="h-3 w-3" /> {t("Dividends")}
          </button>
        </div>
        {tab === "announcements" ? (
          announcements && announcements.length > 0 ? (
            <div className="space-y-2">
              {announcements.map((n) => {
                const RowInner = (
                  <>
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-elevated text-xs font-bold text-text-secondary">
                      {(n.symbol ?? upper)[0]}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="line-clamp-2 text-sm leading-snug text-text-primary">
                        {t(n.title)}
                      </div>
                      <div className="mt-0.5 text-[11px] text-text-muted">
                        {formatTimeAgo(n.posted_at)}
                      </div>
                    </div>
                    <span className="shrink-0 self-start rounded-[4px] bg-neutral/20 px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                      {t(n.category ?? "Corporate")}
                    </span>
                  </>
                );
                const rowClass =
                  "flex items-start gap-3 rounded-[8px] border border-border bg-surface-alt p-3 transition-colors";
                return n.url ? (
                  <a
                    key={n.id}
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={cn(rowClass, "hover:border-white/[0.16] hover:bg-hover")}
                  >
                    {RowInner}
                  </a>
                ) : (
                  <div key={n.id} className={rowClass}>
                    {RowInner}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-4 text-center text-text-muted text-sm">
              {t("No recent announcements.")}
            </div>
          )
        ) : tab === "filings" ? (
          <FilingsTab symbol={upper} />
        ) : tab === "financials" ? (
          <FinancialsTab symbol={upper} />
        ) : tab === "news" ? (
          <NewsFeed symbol={upper} />
        ) : (
          <DividendsTab symbol={upper} />
        )}
      </Card>

      {/* Desktop action bar */}
      <Card hover={false} className="hidden lg:block">
        <div className="flex flex-wrap items-center gap-2">
          <ActionButtons
            isInWatchlist={isInWatchlist}
            wlBusy={wlBusy}
            onToggleWatchlist={toggleWatchlist}
            onAddPortfolio={() => navigate({ to: "/portfolio" })}
            onSetAlert={() => {
              if (price != null) setAlertPrice(price.toFixed(2));
              setAlertOpen(true);
            }}
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
            onSetAlert={() => {
              if (price != null) setAlertPrice(price.toFixed(2));
              setAlertOpen(true);
            }}
            compact
            t={t}
          />
        </div>
      </div>

      {/* Price Alert Modal */}
      {alertOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-[12px] border border-border bg-surface p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">
                {t("Set Price Alert")} — {upper}
              </h3>
              <button
                onClick={() => setAlertOpen(false)}
                className="text-text-muted hover:text-text-primary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mb-3 text-xs text-text-secondary">
              {t("Current price")}:{" "}
              <span className="font-mono font-bold text-text-primary">
                {price != null ? formatNumber(price, 2) : "—"}
              </span>
            </p>
            <div className="mb-3 flex gap-2">
              <select
                value={alertCondition}
                onChange={(e) => setAlertCondition(e.target.value as "above" | "below")}
                className="rounded-[6px] border border-border bg-elevated px-2.5 py-1.5 text-xs font-medium text-text-primary"
              >
                <option value="above">{t("Price goes above")}</option>
                <option value="below">{t("Price goes below")}</option>
              </select>
              <input
                type="number"
                step="0.01"
                value={alertPrice}
                onChange={(e) => setAlertPrice(e.target.value)}
                placeholder={t("Target price")}
                className="min-w-0 flex-1 rounded-[6px] border border-border bg-elevated px-2.5 py-1.5 text-xs text-text-primary placeholder:text-text-muted"
              />
            </div>
            {alertMsg && (
              <p
                className={cn(
                  "mb-2 text-xs",
                  alertSeverity === "error"
                    ? "text-bear"
                    : alertSeverity === "success"
                      ? "text-bull"
                      : "text-text-muted",
                )}
              >
                {alertMsg}
              </p>
            )}
            <button
              onClick={handleSetAlert}
              disabled={alertBusy}
              className="flex w-full items-center justify-center gap-2 rounded-[8px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition-all duration-200 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {alertBusy && <Loader2 className="h-4 w-4 animate-spin" />}
              {t("Create Alert")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function DividendsTab({ symbol }: { symbol: string }) {
  const { t } = useLang();
  const { data, isLoading, isError, refetch } = useDividends(symbol);

  if (isLoading) {
    return (
      <div className="py-6 text-center text-sm text-text-secondary">
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
        {t("Loading dividends...")}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="py-4 text-center text-sm text-text-muted">
        <p>{t("Failed to load dividends.")}</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 inline-flex items-center gap-1 rounded-[6px] border border-border px-2.5 py-1 text-xs text-text-secondary hover:bg-hover"
        >
          {t("Retry")}
        </button>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-text-muted">
        {t("No dividends data available for this symbol.")}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-[11px] text-text-muted">
            <th className="py-2 pr-3 font-medium">{t("Ex-Date")}</th>
            <th className="py-2 pr-3 font-medium">{t("Type")}</th>
            <th className="py-2 pr-3 text-right font-medium">{t("Per Share")}</th>
            <th className="py-2 pr-3 text-right font-medium">{t("Bonus %")}</th>
            <th className="py-2 pr-3 font-medium">{t("Ann. Date")}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.announcement_id} className="border-b border-border/50">
              <td className="py-2 pr-3 font-mono text-text-primary">{d.ex_date ?? "—"}</td>
              <td className="py-2 pr-3 text-text-secondary">{t(d.payout_type)}</td>
              <td className="py-2 pr-3 text-right font-mono tabular-nums text-text-secondary">
                {d.per_share != null ? d.per_share.toFixed(2) : "—"}
              </td>
              <td className="py-2 pr-3 text-right font-mono tabular-nums text-text-secondary">
                {d.bonus_pct != null ? `${d.bonus_pct}%` : "—"}
              </td>
              <td className="py-2 pr-3 font-mono text-text-muted">{d.announcement_date ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

