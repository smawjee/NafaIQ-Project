import { useMemo, useState } from "react";
import { STOCKS, fmtNum, type Holding, type Signal } from "@/lib/data";
import { computeSignal } from "@/lib/market/signal";
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
  useSellHolding,
  useCreatePortfolio,
  usePortfolioNetworth,
  usePortfolioHistory,
} from "@/hooks/use-portfolio";
import { usePsxSymbols } from "@/hooks/psx/use-psx";
import type { StockSearchResult } from "@/lib/psx/stock-search";
import { RANGES, ALLOCATION_PALETTE } from "@/features/portfolio/portfolio.data";
import {
  series,
  relativeBenchmarkDiff,
  EMPTY_HOLDING_FORM,
  type HoldingForm,
} from "@/features/portfolio/portfolio.utils";
// Hidden until built for real — HaqeeqiDaulat currently renders hardcoded
// placeholder numbers (returns, devaluation, shield score), not the user's
// actual portfolio. Restore this import + the render below once it's wired to
// real data.
// import { HaqeeqiDaulat } from "@/features/portfolio/components/HaqeeqiDaulat";
import { PortfolioStatCards } from "@/features/portfolio/components/PortfolioStatCards";
import { PortfolioPerformanceCard } from "@/features/portfolio/components/PortfolioPerformanceCard";
import { PortfolioAllocationCards } from "@/features/portfolio/components/PortfolioAllocationCards";
import { PortfolioHoldingsTable } from "@/features/portfolio/components/PortfolioHoldingsTable";
import { PortfolioHoldingFormModal } from "@/features/portfolio/components/PortfolioHoldingFormModal";
import {
  PortfolioRemoveHoldingModal,
  type RemoveHoldingTarget,
} from "@/features/portfolio/components/PortfolioRemoveHoldingModal";
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
  const sellHoldingApi = useSellHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();

  // Real PSX sectors, keyed by symbol. STOCKS is the ~20-symbol static demo
  // dataset, so looking sectors up there labelled every genuine PSX holding
  // outside that handful "Other" — MEHT (TEXTILE COMPOSITE), OBOY (OIL & GAS
  // MARKETING COMPANIES) and TSBL all fell through while OGDC happened to be
  // in the fixture. /api/symbols carries the sector for all ~1077 tickers, and
  // the allocation donut below was already using it; only this table wasn't.
  const sectorMap = useMemo(
    () => new Map((symbols ?? []).map((s) => [s.symbol, s.sector ?? "Other"])),
    [symbols],
  );

  const apiPortfolioHoldings: Holding[] = (apiHoldings ?? []).map((h) => ({
    ticker: h.symbol,
    sector: sectorMap.get(h.symbol) ?? "Other",
    shares: h.shares,
    avgCost: h.avg_cost,
    current: portfolioValue?.holdings.find((v) => v.id === h.id)?.current_price ?? h.avg_cost,
    signal: (STOCKS[h.symbol]?.signal ?? computeSignal(h.symbol, h.avg_cost, h.avg_cost)) as Signal,
  }));
  const holdings: Holding[] = useDemoPortfolio ? localHoldings : apiPortfolioHoldings;

  const sectorAllocData = useMemo(() => {
    if (useDemoPortfolio) return local.sectorAllocation;
    if (!holdings.length || !symbols) return [];
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
  }, [useDemoPortfolio, local.sectorAllocation, holdings, symbols, sectorMap]);

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
  const [form, setForm] = useState<HoldingForm>(EMPTY_HOLDING_FORM);
  const [formErr, setFormErr] = useState("");
  // When the entered buy price looks wildly off the live price we require a
  // second "Add anyway" click instead of silently storing a bad cost basis.
  const [confirmWarn, setConfirmWarn] = useState(false);
  // Removing a holding asks whether it was sold or added by mistake — the two
  // book completely different things, so the user picks explicitly.
  const [removeTarget, setRemoveTarget] = useState<RemoveHoldingTarget | null>(null);

  // Patch form fields and clear any pending error / warning so the sanity
  // check re-runs against the new values.
  function patchForm(p: Partial<HoldingForm>) {
    setForm((f) => ({ ...f, ...p }));
    setFormErr("");
    setConfirmWarn(false);
  }

  function openAdd() {
    setEditIdx(null);
    setForm(EMPTY_HOLDING_FORM);
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

  // Open the sold-or-mistake chooser for a row in the holdings table.
  function openRemove(idx: number) {
    const h = holdings[idx];
    if (!h) return;
    setRemoveTarget({
      holdingId: useDemoPortfolio ? null : (apiHoldings?.[idx]?.id ?? null),
      index: idx,
      symbol: h.ticker,
      shares: h.shares,
      avgCost: h.avgCost,
      currentPrice: h.current,
    });
  }

  // "Just remove it" — added by mistake, so no cash movement is booked. The API
  // also deletes the backing stock transactions and their finance reflections.
  function confirmRemove() {
    if (!removeTarget) return;
    if (removeTarget.holdingId != null) {
      removeHoldingApi.mutate(removeTarget.holdingId);
    } else {
      dispatch(removeHolding(removeTarget.index));
    }
    setRemoveTarget(null);
  }

  // "I sold it" — a real exit. The API records a sell lot at this price and
  // books the proceeds as income. The demo portfolio has no server state, so it
  // just drops the row locally.
  function confirmSell(price: number, fees: number) {
    if (!removeTarget) return;
    if (removeTarget.holdingId != null) {
      sellHoldingApi.mutate(
        { holdingId: removeTarget.holdingId, price, fees },
        { onSuccess: () => setRemoveTarget(null) },
      );
      return;
    }
    dispatch(removeHolding(removeTarget.index));
    setRemoveTarget(null);
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

      <PortfolioStatCards
        useDemoPortfolio={useDemoPortfolio}
        portfolioValue={portfolioValue}
        networth={networth}
        local={local}
      />

      <PortfolioPerformanceCard
        range={range}
        onRangeChange={setRange}
        benchmarkDiff={benchmarkDiff}
        shouldUseUserPerformance={shouldUseUserPerformance}
        performanceData={performanceData}
        portfolioHistoryLoading={portfolioHistoryLoading}
      />

      {/* Haqeeqi Daulat hidden — placeholder data only, not wired to the real
          portfolio. Restore <HaqeeqiDaulat /> (and its import above) when built. */}

      <PortfolioAllocationCards
        useDemoPortfolio={useDemoPortfolio}
        sectorAllocData={sectorAllocData}
        stockAllocData={stockAllocData}
      />

      <PortfolioHoldingsTable
        holdings={holdings}
        useDemoPortfolio={useDemoPortfolio}
        apiHoldings={apiHoldings}
        onEdit={openEdit}
        onDelete={openRemove}
        onAdd={openAdd}
      />

      <PortfolioHoldingFormModal
        open={formOpen}
        editIdx={editIdx}
        form={form}
        formErr={formErr}
        confirmWarn={confirmWarn}
        onClose={() => setFormOpen(false)}
        onPatch={patchForm}
        onPickStock={pickStock}
        onChangeSymbol={() => setForm({ ...form, ticker: "", sector: "" })}
        onSave={saveHolding}
      />

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

      <PortfolioRemoveHoldingModal
        target={removeTarget}
        pending={sellHoldingApi.isPending || removeHoldingApi.isPending}
        onClose={() => setRemoveTarget(null)}
        onSell={confirmSell}
        onRemove={confirmRemove}
      />
    </div>
  );
}
