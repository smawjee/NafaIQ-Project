import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  Sparkles,
  Loader2,
  X,
  Pencil,
  Trash2,
  Plus,
  ShieldAlert,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";
import { Card, StatCard } from "@/components/shared/Card";
import { Change } from "@/components/charts/Change";
import { SignalBadge } from "@/components/charts/SignalBadge";
import { DonutChart, PortfolioAreaChart } from "@/components/charts/charts";
import { CountUpNumber, AnimatedBar } from "@/components/charts/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { STOCKS, fmtPKR, fmtNum, type Holding, type Signal } from "@/lib/data";
import { cn } from "@/lib/utils";
import { EmojiIcon } from "@/components/icons/icons";
import { useLang } from "@/hooks/use-lang";
import { useFinanceStore, financeActions } from "@/hooks/finance/use-finance-store";
import { useAuth } from "@/hooks/use-auth";
import { usePortfolioList, useHoldings, usePortfolioValue, useAddHolding, useUpdateHolding, useRemoveHolding, useCreatePortfolio, usePortfolioNetworth } from "@/hooks/use-portfolio";
import { usePsxSymbols } from "@/hooks/psx/use-psx";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";

export const Route = createFileRoute("/portfolio")({
  head: () => ({
    meta: [
      { title: "Portfolio — NafaIQ" },
      {
        name: "description",
        content: "Track holdings, performance vs KSE-100, allocation and AI portfolio reports.",
      },
    ],
  }),
  component: Portfolio,
});

const RANGES = ["1M", "3M", "6M", "1Y"] as const;

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function series(n: number) {
  const base = 761190;
  return MONTHS.slice(12 - n).map((label, i, a) => {
    const f = i / (a.length - 1 || 1);
    return {
      label,
      value: Math.round(base * (1 + 0.1273 * f)),
      benchmark: Math.round(base * (1 + 0.095 * f)),
    };
  });
}

const SECTOR_ALLOC = [
  { name: "Banking", value: 20, color: "#00d4aa" },
  { name: "Fertilizer", value: 28, color: "#3b82f6" },
  { name: "Oil & Gas", value: 34, color: "#f59e0b" },
  { name: "Cement", value: 18, color: "#8b5cf6" },
];
const STOCK_ALLOC = [
  { name: "HBL", value: 20, color: "#00d4aa" },
  { name: "ENGRO", value: 13, color: "#3b82f6" },
  { name: "OGDC", value: 34, color: "#f59e0b" },
  { name: "LUCK", value: 18, color: "#8b5cf6" },
  { name: "FFC", value: 15, color: "#6b7280" },
];

const SHIELD_ACTIONS = [
  {
    title: "Add USD-hedged exposure",
    detail: "Shift 10% into export-heavy names (technology, textiles) that earn in USD.",
    points: 12,
  },
  {
    title: "Increase Oil & Gas weighting",
    detail: "Commodity-linked stocks track global prices and cushion rupee weakness.",
    points: 9,
  },
  {
    title: "Trim cash & PKR fixed income",
    detail: "Idle rupee holdings erode fastest during devaluation cycles.",
    points: 7,
  },
  {
    title: "Add gold / commodity proxy",
    detail: "A small allocation to gold-linked assets is a classic inflation hedge.",
    points: 6,
  },
];

function HaqeeqiDaulat() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [applied, setApplied] = useState<number[]>([]);

  const baseScore = 38;
  const gained = applied.reduce((sum, i) => sum + SHIELD_ACTIONS[i].points, 0);
  const score = Math.min(100, baseScore + gained);
  const risk =
    score >= 70 ? t("Low risk") : score >= 45 ? t("Moderate risk") : t("High risk");

  function toggle(i: number) {
    setApplied((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]));
  }

  return (
    <Card hover={false} className="relative overflow-hidden border-gold/20">
      <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gold/10 blur-3xl" />
      <div className="relative z-10">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-gold" strokeWidth={1.75} />
            <h3 className="font-display text-sm font-bold text-text-primary">
              {t("Haqeeqi Daulat™ — Your REAL Returns")}
            </h3>
          </div>
          <span className="rounded-full border border-gold/35 bg-gold/[0.12] px-2.5 py-0.5 text-[10px] font-semibold text-gold">
            {t("After 16.2% PKR devaluation")}
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-[10px] border border-white/[0.06] bg-surface-alt p-4">
            <div className="font-mono text-xl font-bold tabular-nums text-bull">
              <CountUpNumber value={12.73} decimals={2} prefix="+" suffix="%" />
            </div>
            <div className="mt-1 text-[11px] text-text-muted">{t("Nominal PKR Gain")}</div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              +PKR 96,864
            </div>
          </div>
          <div className="rounded-[10px] border border-white/[0.06] bg-surface-alt p-4">
            <div className="font-mono text-xl font-bold tabular-nums text-bear">
              <CountUpNumber value={-16.2} decimals={1} suffix="%" />
            </div>
            <div className="mt-1 text-[11px] text-text-muted">{t("PKR Devaluation")}</div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              -PKR 102,722 eroded
            </div>
          </div>
          <div className="rounded-[10px] border border-white/[0.06] bg-surface-alt p-4">
            <div className="font-mono text-xl font-bold tabular-nums text-bear">
              <CountUpNumber value={-3.2} decimals={1} suffix="%" />
            </div>
            <div className="mt-1 text-[11px] text-text-muted">{t("Real USD Return")}</div>
            <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
              <span dir="ltr">
                <CountUpNumber value={-180} prefix="$" />
              </span>{" "}
              {t("in real terms")}
            </div>
          </div>
        </div>

        <div className="mt-3 rounded-[10px] border border-white/[0.06] bg-surface-alt p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                {t("Devaluation Shield Score")}
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold tabular-nums text-gold">
                  <CountUpNumber value={score} />
                </span>
                <span className="font-mono text-sm text-text-muted">/ 100</span>
                <span className="rounded-full border border-gold/35 bg-gold/[0.12] px-2 py-0.5 text-[10px] font-semibold text-gold">
                  {risk}
                </span>
              </div>
              <p className="mt-1.5 max-w-md text-[11px] text-text-secondary">
                {t("34% of portfolio in Oil & Gas provides partial hedge against rupee weakness.")}
              </p>
            </div>
            <button
              onClick={() => setOpen(true)}
              className="cta-primary flex items-center gap-1.5 rounded-[8px] bg-gold px-3.5 py-2 text-sm font-semibold text-gold-foreground transition hover:bg-gold-hover"
            >
              {t("Improve Score")} <ArrowRight className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
            <AnimatedBar key={score} value={score} className="bg-gold" />
          </div>
        </div>
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={t("Improve Score")}>
        <div className="space-y-3">
          <div className="flex items-baseline justify-between rounded-[8px] border border-gold/25 bg-gold/[0.08] px-3 py-2.5">
            <span className="text-xs text-text-secondary">
              {t("Devaluation Shield Score")}
            </span>
            <span className="font-mono text-lg font-bold tabular-nums text-gold">
              {score}
              <span className="text-xs text-text-muted"> / 100</span>
            </span>
          </div>
          <p className="text-[11px] text-text-muted">
            {t("Apply hedging actions below to project their impact on your shield score.")}
          </p>
          <div className="space-y-2">
            {SHIELD_ACTIONS.map((a, i) => {
              const active = applied.includes(i);
              return (
                <button
                  key={a.title}
                  onClick={() => toggle(i)}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-[8px] border p-3 text-left transition",
                    active
                      ? "border-gold/50 bg-gold/[0.1]"
                      : "border-white/[0.08] bg-surface-alt hover:border-white/20",
                  )}
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold",
                      active
                        ? "border-gold bg-gold text-gold-foreground"
                        : "border-white/20 text-text-muted",
                    )}
                  >
                    {active ? "✓" : "+"}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-text-primary">
                        {t(a.title)}
                      </span>
                      <span className="shrink-0 font-mono text-xs font-semibold text-bull">
                        +{a.points}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] text-text-secondary">{t(a.detail)}</p>
                  </div>
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setOpen(false)}
            className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-[8px] bg-gold px-3.5 py-2.5 text-sm font-semibold text-gold-foreground transition hover:bg-gold-hover"
          >
            {applied.length > 0
              ? `${t("Apply")} ${applied.length} ${t("actions")} — +${gained}`
              : t("Select actions to improve")}
          </button>
        </div>
      </Modal>
    </Card>
  );
}

function computeSignal(ticker: string, current: number, avgCost: number): Signal {
  const stock = STOCKS[ticker.toUpperCase()];
  if (stock) return stock.signal;
  const gainPct = ((current - avgCost) / avgCost) * 100;
  if (gainPct >= 15) return "STRONG BUY";
  if (gainPct >= 5) return "BUY";
  if (gainPct >= -5) return "HOLD";
  if (gainPct >= -15) return "SELL";
  return "STRONG SELL";
}

function Portfolio() {
  const { t } = useLang();
  const { user } = useAuth();
  const { holdings: localHoldings } = useFinanceStore();
  const { data: portfolios } = usePortfolioList();
  const portfolioId = portfolios?.[0]?.id ?? null;
  const { data: apiHoldings } = useHoldings(portfolioId);
  const { data: portfolioValue } = usePortfolioValue(portfolioId);
  const { data: networth } = usePortfolioNetworth(!!user);
  const { data: symbols } = usePsxSymbols();
  const addHoldingApi = useAddHolding(portfolioId);
  const updateHoldingApi = useUpdateHolding(portfolioId);
  const removeHoldingApi = useRemoveHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();

  // For logged-in users: use API data. For anonymous: use localStorage.
  const isLoggedIn = !!user;
  const holdings: Holding[] = isLoggedIn && apiHoldings
    ? apiHoldings.map((h) => ({
        ticker: h.symbol,
        sector: STOCKS[h.symbol]?.sector ?? "Other",
        shares: h.shares,
        avgCost: h.avg_cost,
        current: portfolioValue?.holdings.find((v) => v.id === h.id)?.current_price ?? h.avg_cost,
        signal: (STOCKS[h.symbol]?.signal ?? computeSignal(h.symbol, h.avg_cost, h.avg_cost)) as Signal,
      }))
    : localHoldings;

  const sectorAllocData = useMemo(() => {
    if (!isLoggedIn || !holdings.length || !symbols) return SECTOR_ALLOC;
    const sectorMap = new Map(symbols.map((s) => [s.symbol, s.sector ?? "Other"]));
    const totals = new Map<string, number>();
    for (const h of holdings) {
      const sector = sectorMap.get(h.ticker) ?? "Other";
      const value = (h.current || h.avgCost) * h.shares;
      totals.set(sector, (totals.get(sector) ?? 0) + value);
    }
    const grand = Array.from(totals.values()).reduce((a, b) => a + b, 0);
    if (grand <= 0) return SECTOR_ALLOC;
    const palette = ["#00d4aa", "#3b82f6", "#f59e0b", "#8b5cf6", "#6b7280", "#ec4899", "#10b981"];
    return Array.from(totals.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([name, value], i) => ({
        name,
        value: Math.round((value / grand) * 100),
        color: palette[i % palette.length],
      }));
  }, [isLoggedIn, holdings, symbols]);

  const stockAllocData = useMemo(() => {
    if (!isLoggedIn || !holdings.length) return STOCK_ALLOC;
    const total = holdings.reduce((a, h) => a + (h.current || h.avgCost) * h.shares, 0);
    if (total <= 0) return STOCK_ALLOC;
    const palette = ["#00d4aa", "#3b82f6", "#f59e0b", "#8b5cf6", "#6b7280", "#ec4899", "#10b981"];
    return holdings
      .map((h, i) => ({
        name: h.ticker,
        value: Math.round(((h.current || h.avgCost) * h.shares / total) * 100),
        color: palette[i % palette.length],
      }))
      .sort((a, b) => b.value - a.value);
  }, [isLoggedIn, holdings]);

  const [range, setRange] = useState<(typeof RANGES)[number]>("6M");
  const [reportState, setReportState] = useState<"idle" | "loading" | "open">("idle");
  const n = range === "1M" ? 2 : range === "3M" ? 3 : range === "6M" ? 6 : 12;

  const [formOpen, setFormOpen] = useState(false);
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const emptyForm = {
    ticker: "",
    sector: "",
    shares: "",
    avgCost: "",
    current: "",
  };
  const [form, setForm] = useState(emptyForm);
  const [formErr, setFormErr] = useState("");
  const [deleteIdx, setDeleteIdx] = useState<number | null>(null);

  function openAdd() {
    setEditIdx(null);
    setForm(emptyForm);
    setFormErr("");
    setFormOpen(true);
  }

  function openEdit(idx: number) {
    const h = holdings[idx];
    setEditIdx(idx);
    setForm({
      ticker: h.ticker,
      sector: h.sector,
      shares: String(h.shares),
      avgCost: String(h.avgCost),
      current: String(h.current),
    });
    setFormErr("");
    setFormOpen(true);
  }

  function remove(idx: number) {
    if (isLoggedIn && apiHoldings) {
      removeHoldingApi.mutate(apiHoldings[idx].id);
    } else {
      financeActions.removeHolding(idx);
    }
  }

  function saveHolding() {
    setFormErr("");
    const shares = Number(form.shares);
    const avgCost = Number(form.avgCost);
    const current = Number(form.current);
    if (!form.ticker.trim()) return setFormErr(t("Please enter a stock symbol."));
    if (!form.sector.trim()) return setFormErr(t("Please enter a sector."));
    if (!form.shares || Number.isNaN(shares) || shares <= 0)
      return setFormErr(t("Please enter a valid number of shares."));
    if (!form.avgCost || Number.isNaN(avgCost) || avgCost <= 0)
      return setFormErr(t("Please enter a valid average cost."));
    const cur = !form.current || Number.isNaN(current) || current <= 0 ? avgCost : current;
    const signal = computeSignal(form.ticker.trim().toUpperCase(), cur, avgCost);
    const entry: Holding = {
      ticker: form.ticker.trim().toUpperCase(),
      sector: form.sector.trim(),
      shares,
      avgCost,
      current: cur,
      signal,
    };
    if (isLoggedIn) {
      if (editIdx == null) {
        // Auto-create default portfolio if user has none
        if (!portfolioId) {
          createPortfolio.mutate("Main", {
            onSuccess: (p) => {
              addHoldingApi.mutate({ symbol: entry.ticker, shares: entry.shares, avg_cost: entry.avgCost });
            },
          });
        } else {
          addHoldingApi.mutate({ symbol: entry.ticker, shares: entry.shares, avg_cost: entry.avgCost });
        }
      } else if (apiHoldings) {
        updateHoldingApi.mutate({ holdingId: apiHoldings[editIdx].id, shares: entry.shares, avg_cost: entry.avgCost });
      }
    } else {
      if (editIdx == null) {
        financeActions.addHolding(entry);
      } else {
        financeActions.updateHolding(editIdx, entry);
      }
    }
    setFormOpen(false);
  }

  function generate() {
    setReportState("loading");
    setTimeout(() => setReportState("open"), 2000);
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">{t("Portfolio")}</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Portfolio Value"
          value={<CountUpNumber value={isLoggedIn && portfolioValue ? portfolioValue.totals.market_value : (isLoggedIn && networth ? networth.total_market_value : 858054)} prefix="PKR " />}
          sub={`${t("Total Invested")} ${fmtPKR(isLoggedIn && portfolioValue ? portfolioValue.totals.cost_basis : (isLoggedIn && networth ? networth.total_cost_basis : 761190))}`}
        />
        <StatCard label="Total Invested" value={<CountUpNumber value={isLoggedIn && portfolioValue ? portfolioValue.totals.cost_basis : (isLoggedIn && networth ? networth.total_cost_basis : 761190)} prefix="PKR " />} />
        <StatCard
          label="Total Gain"
          value={<CountUpNumber value={isLoggedIn && portfolioValue ? portfolioValue.totals.unrealized_pnl : (isLoggedIn && networth ? networth.total_unrealized_pnl : 96864)} prefix={isLoggedIn && (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0) >= 0 ? "+PKR " : "PKR "} />}
          sub={isLoggedIn && portfolioValue ? `${portfolioValue.totals.pnl_pct >= 0 ? "+" : ""}${portfolioValue.totals.pnl_pct.toFixed(2)}%` : isLoggedIn && networth ? `${networth.total_unrealized_pnl_pct >= 0 ? "+" : ""}${networth.total_unrealized_pnl_pct.toFixed(2)}%` : "+12.73%"}
          subColor="text-bull"
        />
        <StatCard
          label="Today's P/L"
          value={<CountUpNumber value={isLoggedIn && networth ? Math.round(networth.today_pnl) : 17480} prefix={isLoggedIn && networth && networth.today_pnl >= 0 ? "+PKR " : "PKR "} />}
          sub={isLoggedIn && networth ? `${networth.today_pnl_pct >= 0 ? "+" : ""}${networth.today_pnl_pct.toFixed(2)}%` : "+1.42%"}
          subColor="text-bull"
        />
      </div>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <div>
        <h3 className="text-sm font-semibold text-text-primary">{t("Performance vs KSE-100")}</h3>
            <span className="text-xs text-bull">{t("Outperforming benchmark by +3.2%")}</span>
          </div>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={cn(
                  "rounded-[6px] px-2.5 py-1 text-xs font-medium",
                  range === r
                    ? "bg-bull text-bull-foreground"
                    : "text-text-secondary hover:bg-hover",
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <PortfolioAreaChart data={series(n)} height={280} />
      </Card>

      <HaqeeqiDaulat />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">{t("Allocation by Sector")}</h3>
          <DonutChart data={sectorAllocData} centerValue={`${sectorAllocData.length} sectors`} />
          <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {sectorAllocData.map((s) => (
              <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                {t(s.name)} {s.value}%
              </span>
            ))}
          </div>
        </Card>
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">{t("Allocation by Stock")}</h3>
          <DonutChart data={stockAllocData} centerValue={`${stockAllocData.length} stocks`} />
          <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {stockAllocData.map((s) => (
              <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                {t(s.name)} {s.value}%
              </span>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Holdings")}</h3>
        {holdings.some((h) => h.signal === "SELL" || h.signal === "STRONG SELL") && (
          <div className="mb-3 flex items-center gap-2 rounded-[8px] border border-bear/30 bg-bear/10 px-3 py-2 text-xs text-bear">
            <AlertTriangle className="h-4 w-4 shrink-0" strokeWidth={1.75} />
            <span>
              {holdings
                .filter((h) => h.signal === "SELL" || h.signal === "STRONG SELL")
                .map((h) => h.ticker)
                .join(", ")}{" "}
              {t("— AI signals suggest reviewing these positions.")}
            </span>
          </div>
        )}
        <div className="scrollbar-none overflow-x-auto">
          <table className="w-full min-w-[760px] text-xs">
            <thead>
              <tr className="border-b border-border text-left text-text-muted">
                <th className="py-2">{t("Stock")}</th>
                <th>{t("Sector")}</th>
                <th className="text-right">{t("Shares")}</th>
                <th className="text-right">{t("Avg Cost")}</th>
                <th className="text-right">{t("Current")}</th>
                <th className="text-right">{t("Mkt Value")}</th>
                <th className="text-right">{t("Gain/Loss")}</th>
                <th className="text-center">{t("Signal")}</th>
                <th className="text-right">{t("Action")}</th>
              </tr>
            </thead>
            <tbody>
              {holdings.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-text-muted">
                    {t("No holdings yet. Add your first position.")}
                  </td>
                </tr>
              )}
              {holdings.map((h, idx) => {
                const mv = h.shares * h.current;
                const gain = h.shares * (h.current - h.avgCost);
                const gainPct = ((h.current - h.avgCost) / h.avgCost) * 100;
                const isSell = h.signal === "SELL" || h.signal === "STRONG SELL";
                return (
                  <tr
                    key={`${h.ticker}-${isLoggedIn && apiHoldings ? apiHoldings[idx].id : idx}`}
                    className={cn(
                      "border-b border-border/50",
                      isSell && "border-s-2 border-s-bear bg-bear/[0.04]",
                    )}
                  >
                    <td className={cn("py-2 font-semibold text-bull", isSell && "ps-3")}>{h.ticker}</td>
                    <td className="text-text-secondary">{t(h.sector)}</td>
                    <td className="text-right font-mono tabular-nums text-text-primary">
                      {h.shares.toLocaleString()}
                    </td>
                    <td className="text-right font-mono tabular-nums text-text-secondary">
                      {fmtNum(h.avgCost)}
                    </td>
                    <td className="text-right font-mono tabular-nums text-text-primary">
                      {fmtNum(h.current)}
                    </td>
                    <td className="text-right font-mono tabular-nums text-text-primary">
                      {fmtPKR(mv)}
                    </td>
                    <td className="text-right font-mono tabular-nums">
                      <span className={gain >= 0 ? "text-bull" : "text-bear"}>
                        {gain >= 0 ? "+" : ""}
                        {fmtPKR(gain)} ({gainPct >= 0 ? "+" : ""}
                        {gainPct.toFixed(1)}%)
                      </span>
                    </td>
                    <td className="text-center">
                      <SignalBadge signal={h.signal} />
                    </td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2 text-text-muted">
                        <button
                          onClick={() => openEdit(idx)}
                          aria-label={t("Edit")}
                          className="transition hover:text-text-primary"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => setDeleteIdx(idx)}
                          aria-label={t("Delete")}
                          className="transition hover:text-bear"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <button
          onClick={openAdd}
          className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          <Plus className="h-4 w-4" />
          {t("Add Holding")}
        </button>
      </Card>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editIdx == null ? t("Add Holding") : t("Edit Holding")}
      >
        <div className="space-y-3">
          <input
            value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value })}
            placeholder={t("Stock symbol (e.g. HBL)")}
            className={fieldClass}
          />
          <input
            value={form.sector}
            onChange={(e) => setForm({ ...form, sector: e.target.value })}
            placeholder={t("Sector")}
            className={fieldClass}
          />
          <input
            value={form.shares}
            onChange={(e) => setForm({ ...form, shares: e.target.value })}
            inputMode="decimal"
            placeholder={t("Shares")}
            className={fieldClass}
          />
          <input
            value={form.avgCost}
            onChange={(e) => setForm({ ...form, avgCost: e.target.value })}
            inputMode="decimal"
            placeholder={t("Avg Cost (PKR)")}
            className={fieldClass}
          />
          <input
            value={form.current}
            onChange={(e) => setForm({ ...form, current: e.target.value })}
            inputMode="decimal"
            placeholder={t("Current price (PKR, optional)")}
            className={fieldClass}
          />
          {formErr && <div className="text-xs text-bear">{formErr}</div>}
          <button
            onClick={saveHolding}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {editIdx == null ? t("Add Holding") : t("Save Changes")}
          </button>
        </div>
      </Modal>

      {/* AI report */}
      <div className="rounded-[8px] border border-border border-l-4 border-l-ai bg-ai-tint p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <Sparkles className="h-5 w-5 shrink-0 text-ai" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-text-primary">{t("AI Portfolio Report")}</h3>
            <p className="text-sm text-text-secondary">
              {t(
                "Get a plain-English analysis — diversification score, risk assessment, top opportunities, and suggested rebalancing.",
              )}
            </p>
          </div>
          <button
            onClick={generate}
            disabled={reportState === "loading"}
            className="flex items-center gap-2 rounded-[6px] bg-ai px-4 py-2 text-sm font-semibold text-white hover:brightness-110 disabled:opacity-70"
          >
            {reportState === "loading" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("Analyzing…")}
              </>
            ) : (
              t("Generate Report")
            )}
          </button>
        </div>
      </div>

      {reportState === "open" && <ReportModal onClose={() => setReportState("idle")} />}

      <ConfirmDialog
        open={deleteIdx !== null}
        onOpenChange={(o) => !o && setDeleteIdx(null)}
        onConfirm={() => {
          if (deleteIdx != null) remove(deleteIdx);
          setDeleteIdx(null);
        }}
        title="Delete Holding"
        description="Are you sure you want to delete this holding? This action cannot be undone."
        confirmText="Delete"
      />
    </div>
  );
}

function ReportModal({ onClose }: { onClose: () => void }) {
  const { t } = useLang();
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/70" />
      <div
        className="safe-bottom relative max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-[16px] border border-border bg-surface p-5 pb-8 sm:rounded-[12px]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-semibold text-text-primary">
            {t("AI Portfolio Report")}
          </h3>
          <button onClick={onClose}>
            <X className="h-5 w-5 text-text-secondary" />
          </button>
        </div>
        <div className="rounded-[10px] border border-white/[0.08] bg-surface-alt p-4 text-center">
          <p className="text-sm font-semibold text-text-primary">Coming soon</p>
          <p className="mt-2 text-xs leading-relaxed text-text-secondary">
            Real AI insights from your portfolio holdings are coming soon. For now, review your live KPIs and allocation breakdown above.
          </p>
        </div>
        <div className="mt-4 mb-6 flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 rounded-[10px] border border-white/[0.08] bg-surface py-2 text-sm font-semibold text-text-primary transition-colors hover:border-white/[0.16]"
          >
            {t("Close")}
          </button>
        </div>
      </div>
    </div>
  );
}
