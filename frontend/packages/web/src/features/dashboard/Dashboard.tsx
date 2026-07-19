import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useTheme } from "@/hooks/use-theme";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useDashboardData } from "@/hooks/use-demo-data";
import { usePortfolioHistory, usePortfolioNetworth } from "@/hooks/use-portfolio";
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
import { useSpendingByCategory } from "@/hooks/use-finance-series";
import { useWatchlist, useEnrichedWatchlist } from "@/hooks/psx/use-watchlist";
import { usePsxIndexCards } from "@/hooks/psx/use-psx";
import { RANGES } from "@/features/dashboard/dashboard.data";
import { portfolioSeries, type DashboardGoal } from "@/features/dashboard/dashboard.utils";
import { QuickAddTransactionModal } from "@/features/dashboard/components/QuickAddTransactionModal";
import { QuickAddHoldingModal } from "@/features/dashboard/components/QuickAddHoldingModal";
import { QuickAddAlertModal } from "@/features/dashboard/components/QuickAddAlertModal";
import { DashboardRecommendation } from "@/features/dashboard/components/DashboardRecommendation";
import { DashboardHero } from "@/features/dashboard/components/DashboardHero";
import { DashboardMetricCards } from "@/features/dashboard/components/DashboardMetricCards";
import { DashboardCharts } from "@/features/dashboard/components/DashboardCharts";
import { DashboardWatchlistStrip } from "@/features/dashboard/components/DashboardWatchlistStrip";
import { DashboardGoals } from "@/features/dashboard/components/DashboardGoals";
import { MacroWidget } from "@/features/dashboard/MacroWidget";
import { UnusualActivityWidget } from "@/features/psx/UnusualActivityWidget";
import { NewsFeed } from "@/features/psx/NewsFeed";

export function Dashboard() {
  const { profile, user } = useAuth();
  const { isDemo } = useDemo();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const useShowcaseDashboard = isDemo;

  // Onboarding: real users who haven't chosen a plan yet pick one first;
  // everything downstream is gated by that choice.
  const needsPlanSelection = !!user && !isDemo && profile !== null && !profile.plan_selected_at;
  useEffect(() => {
    if (needsPlanSelection) navigate({ to: "/plans" });
  }, [needsPlanSelection, navigate]);
  const firstName = (profile?.display_name || user?.email?.split("@")[0] || "Investor").split(
    " ",
  )[0];
  const [range, setRange] = useState<(typeof RANGES)[number]>("6M");
  const [showAI, setShowAI] = useState(true);
  const months = range === "1M" ? 2 : range === "3M" ? 3 : range === "1Y" ? 6 : 6;
  const historyDays = range === "1M" ? 30 : range === "3M" ? 90 : range === "1Y" ? 365 : 180;

  /* Quick-add modal state */
  const [txOpen, setTxOpen] = useState(false);
  const [holdingOpen, setHoldingOpen] = useState(false);
  const [alertOpen, setAlertOpen] = useState(false);

  /* Real user data hooks (demo stays on showcase data) */
  const realUserEnabled = !!user && !isDemo;
  const { data: networth } = usePortfolioNetworth(realUserEnabled);
  const { data: portfolioHistory, isLoading: portfolioHistoryLoading } = usePortfolioHistory(
    historyDays,
    realUserEnabled,
  );
  const { data: financeSummary } = useFinanceSummary(undefined, realUserEnabled);
  const { data: spendingByCat, isLoading: spendingByCatLoading } = useSpendingByCategory(
    30,
    realUserEnabled,
  );
  const { data: userGoals } = useFinanceGoals(realUserEnabled);
  const { symbols: userWatchlist, remove: removeFromWatchlist } = useWatchlist();
  const { data: enrichedWatchlist, isLoading: watchlistLoading } =
    useEnrichedWatchlist(realUserEnabled);
  // Lightweight cards endpoint — latest/prev close only, not full history.
  const { data: indexCards } = usePsxIndexCards();
  const kse100ChangePct = indexCards?.find((c) => c.code === "KSE100")?.change_pct ?? null;
  const kse100ChangeLabel =
    kse100ChangePct == null
      ? "--"
      : `${kse100ChangePct >= 0 ? "+" : ""}${kse100ChangePct.toFixed(2)}%`;
  // Demo/local dashboard numbers come from the global Redux store, so demo
  // activity (transactions, buys, watchlist edits) updates them live.
  const showcase = useDashboardData();
  const portfolioChartData = !useShowcaseDashboard
    ? (portfolioHistory?.points ?? [])
    : portfolioSeries(months, showcase.portfolioValue);
  const dashboardWatchlist = useShowcaseDashboard
    ? showcase.watchlistSymbols
    : (enrichedWatchlist ?? []);
  const dashboardGoals: DashboardGoal[] = !useShowcaseDashboard
    ? (userGoals ?? []).slice(0, 3).map((g) => ({
        emoji: g.emoji || "",
        name: g.name,
        saved: g.saved,
        target: g.target,
        color: (g.color === "warning" ? "warning" : "bull") as "warning" | "bull",
        ai: g.ai_tip || "",
      }))
    : showcase.goals;

  // KPI values, resolved once for both modes (demo -> Redux, real -> API).
  const kpiNetWorth = useShowcaseDashboard
    ? showcase.netWorth
    : (networth?.total_market_value ?? 0);
  const kpiPortfolioValue = useShowcaseDashboard
    ? showcase.portfolioValue
    : (networth?.total_market_value ?? 0);
  const kpiTotalInvested = useShowcaseDashboard
    ? showcase.totalInvested
    : (networth?.total_cost_basis ?? 0);
  const kpiMonthlySpending = useShowcaseDashboard
    ? showcase.monthlySpending
    : (financeSummary?.expenses ?? 0);
  const kpiTodayPnl = useShowcaseDashboard ? showcase.todayPnl : (networth?.today_pnl ?? 0);
  const kpiTodayPnlPct = useShowcaseDashboard
    ? showcase.todayPnlPct
    : (networth?.today_pnl_pct ?? 0);
  const kpiUnrealizedPct = useShowcaseDashboard
    ? showcase.unrealizedPnlPct
    : (networth?.total_unrealized_pnl_pct ?? 0);
  const kpiSpendingDeltaPct = useShowcaseDashboard
    ? showcase.monthlySpendingDeltaPct
    : financeSummary && financeSummary.last_month_expense > 0
      ? Math.round(
          ((financeSummary.expenses - financeSummary.last_month_expense) /
            financeSummary.last_month_expense) *
            100,
        )
      : 0;

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <DashboardHero
        firstName={firstName}
        kse100ChangePct={kse100ChangePct}
        kse100ChangeLabel={kse100ChangeLabel}
        onAddTransaction={() => setTxOpen(true)}
        onAddHolding={() => setHoldingOpen(true)}
        onAddAlert={() => setAlertOpen(true)}
      />

      {/* AI Insight — verified cross-domain nudge (spec §3.5) */}
      <DashboardRecommendation enabled={showAI} onDismiss={() => setShowAI(false)} />

      <DashboardMetricCards
        showWelcome={!!(user && !isDemo && networth && networth.holding_count === 0)}
        netWorth={kpiNetWorth}
        portfolioValue={kpiPortfolioValue}
        totalInvested={kpiTotalInvested}
        monthlySpending={kpiMonthlySpending}
        todayPnl={kpiTodayPnl}
        todayPnlPct={kpiTodayPnlPct}
        unrealizedPct={kpiUnrealizedPct}
        spendingDeltaPct={kpiSpendingDeltaPct}
        onAddHolding={() => setHoldingOpen(true)}
        onAddTransaction={() => setTxOpen(true)}
      />

      <DashboardCharts
        range={range}
        onRangeChange={setRange}
        useShowcaseDashboard={useShowcaseDashboard}
        portfolioHistoryLoading={portfolioHistoryLoading}
        portfolioChartData={portfolioChartData}
        spendingByCatLoading={spendingByCatLoading}
        spendingByCat={spendingByCat}
        showcaseSpending={showcase.spending}
        theme={theme}
      />

      {/* Workstream D: macro snapshot + unusual activity + latest news */}
      <div className="grid gap-4 lg:grid-cols-3">
        <MacroWidget />
        <UnusualActivityWidget />
        <NewsFeed limit={6} />
      </div>

      <DashboardWatchlistStrip
        watchlistLoading={watchlistLoading}
        watchlist={dashboardWatchlist}
        useShowcaseDashboard={useShowcaseDashboard}
        onRemove={removeFromWatchlist}
      />

      <DashboardGoals hasUser={!!user} goals={dashboardGoals} />

      <QuickAddTransactionModal open={txOpen} onClose={() => setTxOpen(false)} />
      <QuickAddHoldingModal open={holdingOpen} onClose={() => setHoldingOpen(false)} />
      <QuickAddAlertModal open={alertOpen} onClose={() => setAlertOpen(false)} />
    </div>
  );
}
