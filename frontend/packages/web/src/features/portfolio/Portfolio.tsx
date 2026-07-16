import { useMemo, useState } from "react";
import { Pencil, Trash2, Plus, AlertTriangle } from "lucide-react";
import { Card, StatCard } from "@/components/shared/Card";
import { SignalBadge } from "@/components/market/SignalBadge";
import { DonutChart, PortfolioAreaChart } from "@/components/charts/charts";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { STOCKS, fmtPKR, fmtNum, type Holding, type Signal } from "@/lib/data";
import { computeSignal } from "@/lib/market/signal";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useAppDispatch } from "@/store/hooks";
import { addHolding, updateHolding, removeHolding } from "@/store/portfolio";
import { usePortfolioData } from "@/hooks/use-demo-data";
import {
  usePortfolioList,
  useHoldings,
  usePortfolioValue,
  useAddHolding,
  useUpdateHolding,
  useRemoveHolding,
  useCreatePortfolio,
  usePortfolioNetworth,
  usePortfolioHistory,
} from "@/hooks/use-portfolio";
import { usePsxSymbols } from "@/hooks/psx/use-psx";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { StockSearchBox } from "@/components/search/StockSearchBox";
import { StockLogo } from "@/components/search/StockLogo";
import type { StockSearchResult } from "@/lib/psx/stock-search";
import { RANGES, ALLOCATION_PALETTE } from "@/features/portfolio/portfolio.data";
import { series, relativeBenchmarkDiff } from "@/features/portfolio/portfolio.utils";
import { HaqeeqiDaulat } from "@/features/portfolio/components/HaqeeqiDaulat";
import { ReportPanel } from "@/components/ai/ReportPanel";
import { usePortfolioReport } from "@/hooks/ai/use-ai-report";

export function Portfolio() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  // Demo/local portfolio data (holdings, KPIs, allocations) comes from the
  // global Redux store, so demo buys/sells update every widget on this page.
  const local = usePortfolioData();
  const localHoldings = local.holdings;
  const isLoggedIn = !!user;
  const useDemoPortfolio = isDemo;
  const realPortfolioEnabled = isLoggedIn && !isDemo;
  const { data: portfolios } = usePortfolioList(realPortfolioEnabled);
  const portfolioId = portfolios?.[0]?.id ?? null;
  const { data: apiHoldings } = useHoldings(portfolioId, realPortfolioEnabled);
  const { data: portfolioValue } = usePortfolioValue(portfolioId, realPortfolioEnabled);
  const { data: networth } = usePortfolioNetworth(realPortfolioEnabled);
  const { data: symbols } = usePsxSymbols();
  const addHoldingApi = useAddHolding(portfolioId);
  const updateHoldingApi = useUpdateHolding(portfolioId);
  const removeHoldingApi = useRemoveHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();

  const apiPortfolioHoldings: Holding[] = (apiHoldings ?? []).map((h) => ({
    ticker: h.symbol,
    sector: STOCKS[h.symbol]?.sector ?? "Other",
    shares: h.shares,
    avgCost: h.avg_cost,
    current: portfolioValue?.holdings.find((v) => v.id === h.id)?.current_price ?? h.avg_cost,
    signal: (STOCKS[h.symbol]?.signal ?? computeSignal(h.symbol, h.avg_cost, h.avg_cost)) as Signal,
  }));
  const holdings: Holding[] = useDemoPortfolio ? localHoldings : apiPortfolioHoldings;

  const sectorAllocData = useMemo(() => {
    if (useDemoPortfolio) return local.sectorAllocation;
    if (!holdings.length || !symbols) return [];
    const sectorMap = new Map((symbols ?? []).map((s) => [s.symbol, s.sector ?? "Other"]));
    const totals = new Map<string, number>();
    for (const h of holdings) {
      const sector = sectorMap.get(h.ticker) ?? "Other";
      const value = (h.current || h.avgCost) * h.shares;
      totals.set(sector, (totals.get(sector) ?? 0) + value);
    }
    const grand = Array.from(totals.values()).reduce((a, b) => a + b, 0);
    if (grand <= 0) return [];
    const palette = ALLOCATION_PALETTE;
    return Array.from(totals.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([name, value], i) => ({
        name,
        value: Math.round((value / grand) * 100),
        color: palette[i % palette.length],
      }));
  }, [useDemoPortfolio, local.sectorAllocation, holdings, symbols]);

  const stockAllocData = useMemo(() => {
    if (useDemoPortfolio) return local.stockAllocation;
    if (!holdings.length) return [];
    const total = holdings.reduce((a, h) => a + (h.current || h.avgCost) * h.shares, 0);
    if (total <= 0) return [];
    const palette = ALLOCATION_PALETTE;
    return holdings
      .map((h, i) => ({
        name: h.ticker,
        value: Math.round((((h.current || h.avgCost) * h.shares) / total) * 100),
        color: palette[i % palette.length],
      }))
      .sort((a, b) => b.value - a.value);
  }, [useDemoPortfolio, local.stockAllocation, holdings]);

  const [range, setRange] = useState<(typeof RANGES)[number]>("6M");
  const n = range === "1M" ? 2 : range === "3M" ? 3 : range === "6M" ? 6 : 12;
  const historyDays = range === "1M" ? 30 : range === "3M" ? 90 : range === "1Y" ? 365 : 180;
  const reportMutation = usePortfolioReport(historyDays);
  const shouldUseUserPerformance = isLoggedIn && !isDemo;
  const { data: portfolioHistory, isLoading: portfolioHistoryLoading } = usePortfolioHistory(
    historyDays,
    shouldUseUserPerformance,
  );
  const performanceData = shouldUseUserPerformance
    ? (portfolioHistory?.points ?? [])
    : series(n, local.totalInvested);
  const benchmarkDiff = shouldUseUserPerformance ? relativeBenchmarkDiff(performanceData) : 3.2;

  const [formOpen, setFormOpen] = useState(false);
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const emptyForm = {
    ticker: "",
    sector: "",
    shares: "",
    // Cost basis can be entered as a per-share price OR a total amount paid;
    // `costMode` picks which field is authoritative (see saveHolding()).
    costMode: "per_share" as "per_share" | "total",
    buyPrice: "",
    totalCost: "",
    current: "",
  };
  const [form, setForm] = useState(emptyForm);
  const [formErr, setFormErr] = useState("");
  // When the entered buy price looks wildly off the live price we require a
  // second "Add anyway" click instead of silently storing a bad cost basis.
  const [confirmWarn, setConfirmWarn] = useState(false);
  const [deleteIdx, setDeleteIdx] = useState<number | null>(null);

  // Patch form fields and clear any pending error / warning so the sanity
  // check re-runs against the new values.
  function patchForm(p: Partial<typeof emptyForm>) {
    setForm((f) => ({ ...f, ...p }));
    setFormErr("");
    setConfirmWarn(false);
  }

  function openAdd() {
    setEditIdx(null);
    setForm(emptyForm);
    setFormErr("");
    setConfirmWarn(false);
    setFormOpen(true);
  }

  function openEdit(idx: number) {
    const h = holdings[idx];
    setEditIdx(idx);
    setForm({
      ticker: h.ticker,
      sector: h.sector,
      shares: String(h.shares),
      costMode: "per_share",
      buyPrice: String(h.avgCost),
      totalCost: "",
      current: String(h.current),
    });
    setFormErr("");
    setConfirmWarn(false);
    setFormOpen(true);
  }

  // Chosen from the searchable PSX universe → fill symbol, sector, and (if the
  // live snapshot has it) the current price, so the user never types a raw ticker.
  function pickStock(r: StockSearchResult) {
    setFormErr("");
    setForm((f) => ({
      ...f,
      ticker: r.symbol,
      sector: r.sector ?? f.sector ?? "Other",
      current: r.price != null && r.price > 0 ? String(r.price) : f.current,
    }));
  }

  function remove(idx: number) {
    if (!useDemoPortfolio && apiHoldings?.[idx]) {
      removeHoldingApi.mutate(apiHoldings[idx].id);
    } else {
      dispatch(removeHolding(idx));
    }
  }

  function saveHolding() {
    setFormErr("");
    const shares = Number(form.shares);
    const current = Number(form.current);
    if (!form.ticker.trim()) return setFormErr(t("Please enter a stock symbol."));
    if (!form.sector.trim()) return setFormErr(t("Please enter a sector."));
    if (!form.shares || Number.isNaN(shares) || shares <= 0)
      return setFormErr(t("Please enter a valid number of shares."));

    // Resolve the per-share buy price from the chosen entry mode. In "total"
    // mode the user typed the total amount paid, so buyPrice = total / shares.
    let buyPrice: number;
    if (form.costMode === "total") {
      const total = Number(form.totalCost);
      if (!form.totalCost || Number.isNaN(total) || total <= 0)
        return setFormErr(t("Please enter a valid total cost."));
      buyPrice = total / shares;
    } else {
      buyPrice = Number(form.buyPrice);
      if (!form.buyPrice || Number.isNaN(buyPrice) || buyPrice <= 0)
        return setFormErr(t("Please enter a valid buy price."));
    }
    // Round to the stored precision (avg_cost is Numeric(12,2) on the backend).
    buyPrice = Math.round(buyPrice * 100) / 100;
    if (!Number.isFinite(buyPrice) || buyPrice <= 0)
      return setFormErr(t("Please enter a valid buy price."));

    // Current price: entered value, else the live/auto price captured when the
    // stock was picked, else fall back to the buy price.
    const cur = !form.current || Number.isNaN(current) || current <= 0 ? buyPrice : current;

    // Sanity guard against the classic wrong-field mistake (entering a total as
    // a per-share price, or vice-versa). When a live price is known and the
    // per-share buy price is >5x off in either direction, require an explicit
    // confirmation rather than silently storing a bad cost basis.
    const livePrice = current > 0 ? current : 0;
    if (livePrice > 0 && (buyPrice > livePrice * 5 || buyPrice < livePrice / 5) && !confirmWarn) {
      setConfirmWarn(true);
      return setFormErr(
        t("Buy price PKR {price} is far from the current price PKR {current}. Add anyway?")
          .replace("{price}", fmtNum(buyPrice))
          .replace("{current}", fmtNum(livePrice)),
      );
    }

    const signal = computeSignal(form.ticker.trim().toUpperCase(), cur, buyPrice);
    const entry: Holding = {
      ticker: form.ticker.trim().toUpperCase(),
      sector: form.sector.trim(),
      shares,
      avgCost: buyPrice,
      current: cur,
      signal,
    };
    if (!useDemoPortfolio) {
      if (editIdx == null) {
        // Auto-create default portfolio if user has none
        if (!portfolioId) {
          createPortfolio.mutate("Main", {
            onSuccess: (p) => {
              addHoldingApi.mutate({
                portfolioId: p.id,
                symbol: entry.ticker,
                shares: entry.shares,
                avg_cost: entry.avgCost,
              });
            },
          });
        } else {
          addHoldingApi.mutate({
            portfolioId,
            symbol: entry.ticker,
            shares: entry.shares,
            avg_cost: entry.avgCost,
          });
        }
      } else if (apiHoldings?.[editIdx]) {
        updateHoldingApi.mutate({
          holdingId: apiHoldings[editIdx].id,
          shares: entry.shares,
          avg_cost: entry.avgCost,
        });
      }
    } else {
      if (editIdx == null) {
        dispatch(addHolding(entry));
      } else {
        dispatch(updateHolding({ index: editIdx, holding: entry }));
      }
    }
    setFormOpen(false);
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <h1 className="text-2xl font-bold text-text-primary sm:text-3xl">{t("Portfolio")}</h1>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Portfolio Value"
          value={
            <CountUpNumber
              value={
                !useDemoPortfolio
                  ? (portfolioValue?.totals.market_value ?? networth?.total_market_value ?? 0)
                  : local.marketValue
              }
              prefix="PKR "
            />
          }
          sub={`${t("Total Invested")} ${fmtPKR(!useDemoPortfolio ? (portfolioValue?.totals.cost_basis ?? networth?.total_cost_basis ?? 0) : local.totalInvested)}`}
        />
        <StatCard
          label="Total Invested"
          value={
            <CountUpNumber
              value={
                !useDemoPortfolio
                  ? (portfolioValue?.totals.cost_basis ?? networth?.total_cost_basis ?? 0)
                  : local.totalInvested
              }
              prefix="PKR "
            />
          }
        />
        <StatCard
          label="Total Gain"
          info="Unrealized profit or loss — your holdings' current value minus what you paid."
          value={
            <CountUpNumber
              value={
                !useDemoPortfolio
                  ? (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0)
                  : Math.round(local.unrealizedPnl)
              }
              prefix={
                (!useDemoPortfolio
                  ? (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0)
                  : local.unrealizedPnl) >= 0
                  ? "+PKR "
                  : "PKR "
              }
            />
          }
          sub={
            !useDemoPortfolio && portfolioValue
              ? `${portfolioValue.totals.pnl_pct >= 0 ? "+" : ""}${portfolioValue.totals.pnl_pct.toFixed(2)}%`
              : !useDemoPortfolio && networth
                ? `${networth.total_unrealized_pnl_pct >= 0 ? "+" : ""}${networth.total_unrealized_pnl_pct.toFixed(2)}%`
                : !useDemoPortfolio
                  ? "0.00%"
                  : `${local.unrealizedPnlPct >= 0 ? "+" : ""}${local.unrealizedPnlPct.toFixed(2)}%`
          }
          subColor={
            !useDemoPortfolio
              ? (portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0) >= 0
                ? "text-bull"
                : "text-bear"
              : local.unrealizedPnl >= 0
                ? "text-bull"
                : "text-bear"
          }
        />
        <StatCard
          label="Today's P/L"
          info="Change in your holdings' value today versus yesterday's closing prices."
          value={
            <CountUpNumber
              value={
                !useDemoPortfolio
                  ? Math.round(networth?.today_pnl ?? 0)
                  : Math.round(local.todayPnl)
              }
              prefix={
                (!useDemoPortfolio ? (networth?.today_pnl ?? 0) : local.todayPnl) >= 0
                  ? "+PKR "
                  : "PKR "
              }
            />
          }
          sub={
            !useDemoPortfolio && networth
              ? `${networth.today_pnl_pct >= 0 ? "+" : ""}${networth.today_pnl_pct.toFixed(2)}%`
              : !useDemoPortfolio
                ? "0.00%"
                : `${local.todayPnlPct >= 0 ? "+" : ""}${local.todayPnlPct.toFixed(2)}%`
          }
          subColor={
            !useDemoPortfolio && networth
              ? (networth.today_pnl_pct ?? 0) >= 0
                ? "text-bull"
                : "text-bear"
              : useDemoPortfolio && local.todayPnl < 0
                ? "text-bear"
                : "text-bull"
          }
        />
      </div>

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">
              {t("Performance vs KSE-100")}
            </h3>
            <span
              className={cn(
                "text-xs",
                benchmarkDiff == null
                  ? "text-text-muted"
                  : benchmarkDiff >= 0
                    ? "text-bull"
                    : "text-bear",
              )}
            >
              {shouldUseUserPerformance
                ? benchmarkDiff == null
                  ? t("Add holdings to compare performance with KSE-100")
                  : `${benchmarkDiff >= 0 ? t("Outperforming") : t("Underperforming")} ${t("benchmark by")} ${benchmarkDiff >= 0 ? "+" : ""}${benchmarkDiff.toFixed(2)}%`
                : t("Outperforming benchmark by +3.2%")}
            </span>
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
        {shouldUseUserPerformance && portfolioHistoryLoading ? (
          <div className="flex h-[280px] items-center justify-center text-sm text-text-secondary">
            {t("Loading portfolio history...")}
          </div>
        ) : shouldUseUserPerformance && performanceData.length === 0 ? (
          <div className="flex h-[280px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
            {t("No portfolio history yet. Add holdings to build your performance chart.")}
          </div>
        ) : (
          <PortfolioAreaChart data={performanceData} height={280} />
        )}
      </Card>

      <HaqeeqiDaulat />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">
            {t("Allocation by Sector")}
          </h3>
          {!useDemoPortfolio && sectorAllocData.length === 0 ? (
            <div className="flex h-[220px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
              {t("No sector allocation yet. Add holdings to see your portfolio mix.")}
            </div>
          ) : (
            <>
              <DonutChart
                data={sectorAllocData}
                centerValue={`${sectorAllocData.length} sectors`}
              />
              <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                {sectorAllocData.map((s) => (
                  <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                    <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                    {t(s.name)} {s.value}%
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>
        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-primary">
            {t("Allocation by Stock")}
          </h3>
          {!useDemoPortfolio && stockAllocData.length === 0 ? (
            <div className="flex h-[220px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
              {t("No stock allocation yet. Add holdings to see your stock weights.")}
            </div>
          ) : (
            <>
              <DonutChart data={stockAllocData} centerValue={`${stockAllocData.length} stocks`} />
              <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                {stockAllocData.map((s) => (
                  <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                    <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                    {t(s.name)} {s.value}%
                  </span>
                ))}
              </div>
            </>
          )}
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
              {t("— rule-based indicators suggest reviewing these positions.")}
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
                const gainPct = h.avgCost > 0 ? ((h.current - h.avgCost) / h.avgCost) * 100 : 0;
                const isSell = h.signal === "SELL" || h.signal === "STRONG SELL";
                return (
                  <tr
                    key={`${h.ticker}-${!useDemoPortfolio && apiHoldings?.[idx] ? apiHoldings[idx].id : idx}`}
                    className={cn(
                      "border-b border-border/50",
                      isSell && "border-s-2 border-s-bear bg-bear/[0.04]",
                    )}
                  >
                    <td className={cn("py-2 font-semibold text-bull", isSell && "ps-3")}>
                      {h.ticker}
                    </td>
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
          {editIdx != null ? (
            // Editing: the symbol is fixed — show it read-only.
            <div className="flex items-center gap-2 rounded-[8px] border border-white/[0.08] bg-surface px-3 py-2">
              <StockLogo symbol={form.ticker} size={22} />
              <span className="text-sm font-semibold text-bull">{form.ticker}</span>
              {form.sector && (
                <span className="ml-auto text-[11px] text-text-muted">{form.sector}</span>
              )}
            </div>
          ) : form.ticker ? (
            // Adding, symbol chosen: show the pick with a "Change" affordance.
            <div className="flex items-center gap-2 rounded-[8px] border border-white/[0.08] bg-surface px-3 py-2">
              <StockLogo symbol={form.ticker} size={22} />
              <span className="text-sm font-semibold text-bull">{form.ticker}</span>
              {form.sector && <span className="text-[11px] text-text-muted">{form.sector}</span>}
              <button
                type="button"
                onClick={() => setForm({ ...form, ticker: "", sector: "" })}
                className="ml-auto text-xs font-medium text-text-muted hover:text-text-primary"
              >
                {t("Change")}
              </button>
            </div>
          ) : (
            // Adding, no symbol yet: searchable PSX universe (ticker or name).
            <StockSearchBox
              mode="navigate"
              variant="floating"
              autoFocus
              placeholder={t("Search stock by symbol or name…")}
              onSelect={pickStock}
            />
          )}
          <input
            value={form.shares}
            onChange={(e) => patchForm({ shares: e.target.value })}
            inputMode="decimal"
            placeholder={t("Shares")}
            className={fieldClass}
          />
          {/* Cost basis: enter a per-share price or the total amount paid. */}
          <div className="flex rounded-md border border-border bg-elevated p-0.5 text-xs">
            {(["per_share", "total"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => patchForm({ costMode: m })}
                className={cn(
                  "flex-1 rounded-[5px] py-1.5 font-medium transition",
                  form.costMode === m
                    ? "bg-bull text-bull-foreground"
                    : "text-text-secondary hover:text-text-primary",
                )}
              >
                {m === "per_share" ? t("Price per share") : t("Total cost")}
              </button>
            ))}
          </div>
          {form.costMode === "per_share" ? (
            <input
              value={form.buyPrice}
              onChange={(e) => patchForm({ buyPrice: e.target.value })}
              inputMode="decimal"
              placeholder={t("Buy Price per Share (PKR)")}
              className={fieldClass}
            />
          ) : (
            <div className="space-y-1">
              <input
                value={form.totalCost}
                onChange={(e) => patchForm({ totalCost: e.target.value })}
                inputMode="decimal"
                placeholder={t("Total Cost Paid (PKR)")}
                className={fieldClass}
              />
              {Number(form.shares) > 0 && Number(form.totalCost) > 0 && (
                <p className="px-1 text-[11px] text-text-muted">
                  {t("= PKR {p} / share").replace(
                    "{p}",
                    fmtNum(Number(form.totalCost) / Number(form.shares)),
                  )}
                </p>
              )}
            </div>
          )}
          <input
            value={form.current}
            onChange={(e) => patchForm({ current: e.target.value })}
            inputMode="decimal"
            placeholder={t("Current price (PKR, optional)")}
            className={fieldClass}
          />
          {formErr && (
            <div className={cn("text-xs", confirmWarn ? "text-gold" : "text-bear")}>{formErr}</div>
          )}
          <button
            onClick={saveHolding}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {confirmWarn ? t("Add anyway") : editIdx == null ? t("Add Holding") : t("Save Changes")}
          </button>
        </div>
      </Modal>

      {/* AI report */}
      <ReportPanel
        title={t("AI Portfolio Report")}
        blurb={t(
          "Get a plain-English analysis — diversification score, risk assessment, top opportunities, and suggested rebalancing.",
        )}
        reportType="portfolio"
        mutation={reportMutation}
        onCloseReport={() => reportMutation.reset()}
      />

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
