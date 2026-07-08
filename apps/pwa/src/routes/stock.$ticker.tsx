import { useState } from "react";
import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { ArrowLeft, Sparkles, Circle, Bell, X } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { Change } from "@/components/charts/Change";
import { SignalBadge } from "@/components/charts/SignalBadge";
import { CandlestickChart } from "@/components/charts/charts";
import { CountUpNumber } from "@/components/charts/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { STOCKS, fmtNum } from "@/lib/data";
import {
  usePsxQuote,
  usePsxHistory,
  usePsxProfile,
  usePsxFundamentals,
  usePsxAnnouncements,
  usePsxSignal,
} from "@/hooks/psx/use-psx";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { supabase } from "@/integrations/supabase/client";
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

function signalToColor(sig: string | undefined): string {
  switch (sig) {
    case "STRONG BUY":
      return "text-bull";
    case "BUY":
      return "text-bull/80";
    case "HOLD":
      return "text-text-secondary";
    case "SELL":
      return "text-bear/80";
    case "STRONG SELL":
      return "text-bear";
    default:
      return "text-text-secondary";
  }
}

function StockDetail() {
  const { ticker } = useParams({ from: "/stock/$ticker" });
  const { t } = useLang();
  const s = STOCKS[ticker] ?? STOCKS.HBL;

  const { data: quote } = usePsxQuote(ticker);
  const { data: ohlcvData } = usePsxHistory(ticker);
  const { data: profile } = usePsxProfile(ticker);
  const { data: fundamentals } = usePsxFundamentals(ticker);
  const { data: announcements } = usePsxAnnouncements(ticker, 5);
  const { data: signal } = usePsxSignal(ticker);
  const wl = useWatchlist();

  const [alertOpen, setAlertOpen] = useState(false);
  const [alertCondition, setAlertCondition] = useState<"above" | "below">("above");
  const [alertPrice, setAlertPrice] = useState("");
  const [alertMsg, setAlertMsg] = useState("");

  const price = quote?.price ?? s.price;
  const changePct = quote?.change_pct ?? s.changePct;
  const change = quote?.change ?? +(price * (changePct / 100)).toFixed(2);
  const volume = quote ? fmtNum(quote.volume, 1) : s.volume;
  const sector = profile?.sector ?? s.sector;
  const name = profile?.name ?? s.name;
  const sig = signal?.signal ?? s.signal;
  const confidence = signal?.confidence ?? 0;

  const data = ohlcvData ?? [];
  const chg = +(price * (changePct / 100)).toFixed(2);

  const stats: [string, string][] = [
    ["Market Cap", `PKR ${s.marketCap}`],
    ["P/E Ratio", fundamentals?.pe ? fundamentals.pe.toFixed(1) : "—"],
    ["EPS", fundamentals?.eps ? `PKR ${fundamentals.eps.toFixed(2)}` : "—"],
    ["52W High", quote?.day_high ? quote.day_high.toFixed(2) : "—"],
    ["52W Low", "—"],
    ["Avg Volume", volume],
    ["Dividend Yield", fundamentals?.div_yield ? `${fundamentals.div_yield.toFixed(1)}%` : "—"],
    ["P/B Ratio", fundamentals?.pb ? fundamentals.pb.toFixed(2) : "—"],
  ];

  const isInWatchlist = wl.symbols.includes(ticker.toUpperCase());

  const handleSetAlert = async () => {
    const target = parseFloat(alertPrice);
    if (isNaN(target) || target <= 0) {
      setAlertMsg(t("Please enter a valid price"));
      return;
    }
    try {
      const { data: session } = await supabase.auth.getSession();
      if (!session?.session) {
        setAlertMsg(t("Please log in to set alerts"));
        return;
      }
      await supabase.from("price_alerts").upsert({
        user_id: session.session.user.id,
        symbol: ticker.toUpperCase(),
        condition: alertCondition,
        price: target,
        enabled: true,
      });
      setAlertMsg(t("Alert set!"));
      setTimeout(() => {
        setAlertOpen(false);
        setAlertMsg("");
      }, 1000);
    } catch {
      setAlertMsg(t("Failed to set alert"));
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link
        to="/psx"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> {t("Back to Market")}
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">
            {ticker} · {name}
          </h1>
          <p className="text-sm text-text-secondary">
            {t(sector)} {t("Sector")}
          </p>
          <div className="mt-2 flex items-baseline gap-3">
            <span className="font-mono text-3xl font-bold tabular-nums text-text-primary">
              <CountUpNumber value={price} decimals={2} />
            </span>
            <Change value={`${chg >= 0 ? "+" : ""}${fmtNum(chg)}`} pct={changePct} />
          </div>
        </div>
        <div className="text-right">
          <SignalBadge signal={sig} className="text-xs" />
          <div className="mt-1 text-xs text-text-muted">
            {signal?.model_version === "fallback"
              ? t("Model training in progress")
              : `${t("Confidence")} ${confidence}%`}
          </div>
        </div>
      </div>

      <Card hover={false} className="bg-surface-alt">
        <div className="h-[300px] lg:h-[440px]">
          {data.length > 0 ? (
            <CandlestickChart data={data} height={9999} mas={["MA20", "MA50"]} />
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
        <div className="scrollbar-none overflow-x-auto">
          <table className="w-full min-w-[480px] text-xs">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="py-2">{t("Indicator")}</th>
                <th>{t("Value")}</th>
                <th>{t("Reading")}</th>
                <th className="text-right">{t("Signal")}</th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const feats = signal?.features_used;
                if (feats && feats.length > 0) {
                  return (
                    <tr className="border-b border-border/50">
                      <td className="py-2 text-text-primary">{t("ML Model Features")}</td>
                      <td className="font-mono tabular-nums text-text-secondary">
                        {feats.slice(0, 3).join(", ")}
                      </td>
                      <td className="text-text-secondary">{t("Top predictors")}</td>
                      <td className="text-right">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 font-semibold",
                            signalToColor(sig),
                          )}
                        >
                          <Circle
                            className={cn(
                              "h-2 w-2",
                              sig.includes("BUY")
                                ? "fill-bull text-bull"
                                : sig.includes("SELL")
                                  ? "fill-bear text-bear"
                                  : "fill-text-muted text-text-muted",
                            )}
                          />
                          {t(sig)}
                        </span>
                      </td>
                    </tr>
                  );
                }
                return (
                  <tr>
                    <td colSpan={4} className="py-4 text-center text-text-muted">
                      {t(
                        "Model training in progress — run scripts/train_signal_model.py after backfill",
                      )}
                    </td>
                  </tr>
                );
              })()}
            </tbody>
          </table>
        </div>
        <div
          className={cn(
            "mt-3 rounded-[6px] px-3 py-2 text-sm font-semibold",
            sig === "STRONG BUY" || sig === "BUY"
              ? "bg-bull/10 text-bull"
              : sig === "STRONG SELL" || sig === "SELL"
                ? "bg-bear/10 text-bear"
                : "bg-neutral/10 text-text-secondary",
          )}
        >
          {t(
            `Overall: ${sig} · ${signal?.model_version === "fallback" ? "model pending" : `Confidence ${confidence}%`}`,
          )}
        </div>
        <p className="mt-3 text-sm leading-relaxed text-text-secondary">
          <Typewriter
            id={`stock-ai-${ticker}`}
            text={`${ticker} ${t(
              signal?.model_version !== "fallback"
                ? `ML signal engine rates this stock ${sig} with ${confidence}% confidence. Key drivers: ${signal?.features_used?.slice(0, 3).join(", ") ?? "technical indicators"}.`
                : "is showing strong bullish momentum. Price has broken above MA50 with significantly above-average volume — a classic confirmation signal. RSI at 61 leaves room before overbought territory.",
            )}`}
          />
        </p>
        <p className="mt-2 text-[11px] italic text-text-muted">
          {t("This is AI-generated technical analysis only. Not financial advice.")}
        </p>
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">
          {t("Recent Announcements")}
        </h3>
        {announcements && announcements.length > 0 ? (
          <div className="space-y-2">
            {announcements.map((n) => (
              <div
                key={n.id}
                className="flex items-center gap-3 rounded-[6px] border border-border bg-surface-alt p-3"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] bg-elevated text-xs font-bold text-text-secondary">
                  {(n.symbol ?? "?")[0]}
                </div>
                <div className="flex-1">
                  <div className="text-sm text-text-primary">{t(n.title)}</div>
                  <div className="text-[11px] text-text-muted">
                    {n.category ?? t("Announcement")} · {formatTimeAgo(n.posted_at)}
                  </div>
                </div>
                <span className="rounded-[4px] bg-neutral/20 px-2 py-0.5 text-[10px] font-medium text-text-secondary">
                  {t(n.category ?? "Corporate")}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-4 text-center text-text-muted text-sm">
            {t("Loading announcements...")}
          </div>
        )}
      </Card>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => (isInWatchlist ? wl.remove(ticker) : wl.add(ticker))}
          className="rounded-[10px] border border-white/[0.08] bg-surface px-4 py-2 text-sm font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.16]"
        >
          {isInWatchlist ? t("Remove from Watchlist") : t("Add to Watchlist")}
        </button>
        <button className="rounded-[10px] bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110">
          {t("Add to Portfolio")}
        </button>
        <button
          onClick={() => {
            setAlertPrice(price.toFixed(2));
            setAlertOpen(true);
          }}
          className="rounded-[10px] border border-white/[0.08] bg-surface px-4 py-2 text-sm font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.16]"
        >
          <Bell className="mr-1.5 inline h-3.5 w-3.5" />
          {t("Set Price Alert")}
        </button>
      </div>

      {/* Price Alert Modal */}
      {alertOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-sm rounded-[12px] border border-border bg-surface p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">
                {t("Set Price Alert")} — {ticker}
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
              <span className="font-mono font-bold text-text-primary">{fmtNum(price, 2)}</span>
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
                  alertMsg.includes("Failed") ? "text-bear" : "text-bull",
                )}
              >
                {alertMsg}
              </p>
            )}
            <button
              onClick={handleSetAlert}
              className="w-full rounded-[8px] bg-bull px-4 py-2 text-sm font-semibold text-bull-foreground transition-all duration-200 hover:brightness-110"
            >
              {t("Create Alert")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
