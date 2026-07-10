import { useState } from "react";
import { createFileRoute, Link, useNavigate, useParams } from "@tanstack/react-router";
import { ArrowLeft, Sparkles, Bell, X, Loader2, Plus, Star } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/charts/Change";
import { SignalBadge } from "@/components/charts/SignalBadge";
import { CandlestickChart } from "@/components/charts/charts";
import { CountUpNumber } from "@/components/charts/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { StockLogo } from "@/components/search/StockLogo";
import { logoUrlFor } from "@/lib/psx/stock-search";
import { STOCKS } from "@/lib/data";
import { formatNumber, formatSigned, formatSignedPercent, formatCompactPKR } from "@/lib/format";
import {
  usePsxQuote,
  usePsxHistory,
  usePsxProfile,
  usePsxFundamentals,
  usePsxAnnouncements,
  usePsxSignal,
  usePsxSymbols,
} from "@/hooks/psx/use-psx";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { useDemo } from "@/hooks/use-demo";
import { userPost } from "@/lib/psx/client";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";

export const Route = createFileRoute("/stock/$ticker")({
  head: ({ params }) => ({
    meta: [
      { title: `${params.ticker} — NafaIQ` },
      {
        name: "description",
        content: `${params.ticker} price chart, AI technical analysis and signal breakdown on NafaIQ.`,
      },
    ],
  }),
  component: StockDetail,
});

function formatTimeAgo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

function StockDetail() {
  const { ticker } = useParams({ from: "/stock/$ticker" });
  const { t } = useLang();
  const navigate = useNavigate();
  const { isDemo } = useDemo();
  const upper = ticker.toUpperCase();
  const s = STOCKS[ticker];

  const { data: quote } = usePsxQuote(ticker);
  const { data: ohlcvData } = usePsxHistory(ticker);
  const { data: profile } = usePsxProfile(ticker);
  const { data: fundamentals } = usePsxFundamentals(ticker);
  const { data: announcements } = usePsxAnnouncements(ticker, 5);
  const { data: signal } = usePsxSignal(ticker);
  const { data: symbolsData } = usePsxSymbols();
  const wl = useWatchlist();

  const [alertOpen, setAlertOpen] = useState(false);
  const [alertCondition, setAlertCondition] = useState<"above" | "below">("above");
  const [alertPrice, setAlertPrice] = useState("");
  const [alertMsg, setAlertMsg] = useState("");
  const [alertBusy, setAlertBusy] = useState(false);
  const [wlBusy, setWlBusy] = useState(false);

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

  const data = ohlcvData ?? [];

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
    } catch (error) {
      console.error("Set alert error:", error);
      setAlertMsg(t("Could not set alert — you may have reached your plan's alert limit."));
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
                <span className="font-mono text-3xl font-bold tabular-nums text-text-primary">
                  <CountUpNumber value={price} decimals={2} prefix="PKR " />
                </span>
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
        <div className="h-[300px] lg:h-[440px]">
          {data.length > 0 ? (
            <CandlestickChart data={data} height={9999} mas={["MA20", "MA50", "MA100"]} />
          ) : (
            <div className="flex h-full items-center justify-center text-text-muted text-sm">
              {t("Loading chart data...")}
            </div>
          )}
        </div>
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

      <Card>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Sparkles className="h-4 w-4 text-ai" />
          {t("AI Technical Analysis")}
        </h3>
        {modelReady ? (
          <>
            <div
              className={cn(
                "rounded-[6px] px-3 py-2 text-sm font-semibold",
                sig === "STRONG BUY" || sig === "BUY"
                  ? "bg-bull/10 text-bull"
                  : sig === "STRONG SELL" || sig === "SELL"
                    ? "bg-bear/10 text-bear"
                    : "bg-neutral/10 text-text-secondary",
              )}
            >
              {t("Overall")}: {t(sig ?? "HOLD")} · {t("Confidence")} {confidence}%
            </div>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              <Typewriter
                id={`stock-ai-${ticker}`}
                text={`${upper} — ${t(
                  `ML signal engine rates this stock ${sig} with ${confidence}% confidence. Key drivers: ${signal?.features_used?.slice(0, 3).join(", ") ?? "technical indicators"}.`,
                )}`}
              />
            </p>
          </>
        ) : isDemo ? (
          <>
            <div
              className={cn(
                "rounded-[6px] px-3 py-2 text-sm font-semibold",
                sig === "STRONG BUY" || sig === "BUY"
                  ? "bg-bull/10 text-bull"
                  : sig === "STRONG SELL" || sig === "SELL"
                    ? "bg-bear/10 text-bear"
                    : "bg-neutral/10 text-text-secondary",
              )}
            >
              {t("Overall")}: {t(sig ?? "HOLD")}
            </div>
            <p className="mt-3 text-sm leading-relaxed text-text-secondary">
              <Typewriter
                id={`stock-ai-${ticker}`}
                text={t(
                  "Showcase analysis: momentum indicators and moving-average structure suggest a constructive setup. Sign in with a funded account for live model-driven signals.",
                )}
              />
            </p>
          </>
        ) : (
          <div className="rounded-[8px] border border-dashed border-border bg-surface-alt px-4 py-6 text-center">
            <div className="text-sm font-medium text-text-secondary">
              {t("Signal unavailable — model pending")}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-text-muted">
              {t(
                "The ML signal model has not been trained yet, so no technical call is shown for this stock. Train it via scripts/train_signal_model.py after the OHLCV backfill.",
              )}
            </p>
          </div>
        )}
        <p className="mt-3 text-[11px] italic text-text-muted">
          {t("This is AI-generated technical analysis only. Not financial advice.")}
        </p>
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          {t("Recent Announcements")}
        </h3>
        {announcements && announcements.length > 0 ? (
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
                  alertMsg.includes("Failed") ||
                    alertMsg.includes("valid") ||
                    alertMsg.includes("log in")
                    ? "text-bear"
                    : "text-bull",
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

function ActionButtons({
  isInWatchlist,
  wlBusy,
  onToggleWatchlist,
  onAddPortfolio,
  onSetAlert,
  compact = false,
  t,
}: {
  isInWatchlist: boolean;
  wlBusy: boolean;
  onToggleWatchlist: () => void;
  onAddPortfolio: () => void;
  onSetAlert: () => void;
  compact?: boolean;
  t: (s: string) => string;
}) {
  return (
    <>
      <button
        onClick={onToggleWatchlist}
        disabled={wlBusy}
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-[10px] border border-white/[0.08] bg-surface px-4 py-2 text-sm font-semibold text-text-primary transition-all duration-200 hover:border-white/[0.16] disabled:cursor-not-allowed disabled:opacity-60",
          compact ? "flex-1" : "",
        )}
      >
        {wlBusy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Star className={cn("h-3.5 w-3.5", isInWatchlist && "fill-bull text-bull")} />
        )}
        {isInWatchlist ? t("Remove from Watchlist") : t("Add to Watchlist")}
      </button>
      <button
        onClick={onAddPortfolio}
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-[10px] bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:brightness-110",
          compact ? "flex-1" : "",
        )}
      >
        <Plus className="h-3.5 w-3.5" />
        {t("Add to Portfolio")}
      </button>
      <button
        onClick={onSetAlert}
        className={cn(
          "flex items-center justify-center gap-1.5 rounded-[10px] border border-white/[0.08] bg-surface px-4 py-2 text-sm font-semibold text-text-primary transition-all duration-200 hover:border-white/[0.16]",
          compact ? "flex-1" : "",
        )}
      >
        <Bell className="h-3.5 w-3.5" />
        {t("Set Price Alert")}
      </button>
    </>
  );
}
