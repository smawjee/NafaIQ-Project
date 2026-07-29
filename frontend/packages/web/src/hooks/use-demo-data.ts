// Demo/local data facades.
//
// These hooks expose the global Redux store (the source of truth for demo and
// anonymous users) in the shapes the pages render. Components call one of
// these plus their existing React Query hooks, then pick a side with `isDemo`:
// Redux for demo/local mode, React Query for real authenticated users. Real
// user data never flows through these hooks, and demo activity never reaches
// the backend.

import { useMemo } from "react";
import { useAuth } from "@/hooks/use-auth";
import { isDemoUser } from "@/lib/demo";
import { useAppSelector } from "@/store/hooks";
import {
  selectTransactions,
  selectBills,
  selectBudgets,
  selectGoals,
  selectFinanceSummary,
  selectSpendingBreakdown,
} from "@/store/finance";
import {
  selectHoldings,
  selectMarketValue,
  selectTotalInvested,
  selectUnrealizedPnl,
  selectUnrealizedPnlPct,
  selectTodayPnl,
  selectTodayPnlPct,
  selectDemoNetWorth,
  selectSectorAllocation,
  selectStockAllocation,
} from "@/store/portfolio";
import { selectWatchlistSymbols } from "@/store/watchlist";
import { INCOME_EXPENSE } from "@/lib/finance/data";

export { isDemoUser } from "@/lib/demo";

/** Local finance data: transactions, bills, budgets, goals plus summaries
 * computed live from the store, and a 6-month series whose latest month
 * reflects current demo activity. */
export function useFinanceData() {
  const { user } = useAuth();
  const isDemo = isDemoUser(user);
  const transactions = useAppSelector(selectTransactions);
  const bills = useAppSelector(selectBills);
  const budgets = useAppSelector(selectBudgets);
  const goals = useAppSelector(selectGoals);
  const summary = useAppSelector(selectFinanceSummary);
  const spending = useAppSelector(selectSpendingBreakdown);

  const series = useMemo(() => {
    const history = INCOME_EXPENSE.slice(0, -1);
    const latest = INCOME_EXPENSE[INCOME_EXPENSE.length - 1];
    return [...history, { month: latest.month, income: summary.income, expense: summary.expenses }];
  }, [summary]);

  // Previous fixture month, used for "vs last month" comparisons in demo mode.
  const lastMonth = INCOME_EXPENSE[INCOME_EXPENSE.length - 2];

  return { isDemo, transactions, bills, budgets, goals, summary, spending, series, lastMonth };
}

/** Local portfolio data: holdings plus KPIs and allocations computed live
 * from the store. */
export function usePortfolioData() {
  const { user } = useAuth();
  const isDemo = isDemoUser(user);
  const holdings = useAppSelector(selectHoldings);
  const marketValue = useAppSelector(selectMarketValue);
  const totalInvested = useAppSelector(selectTotalInvested);
  const unrealizedPnl = useAppSelector(selectUnrealizedPnl);
  const unrealizedPnlPct = useAppSelector(selectUnrealizedPnlPct);
  const todayPnl = useAppSelector(selectTodayPnl);
  const todayPnlPct = useAppSelector(selectTodayPnlPct);
  const netWorth = useAppSelector(selectDemoNetWorth);
  const sectorAllocation = useAppSelector(selectSectorAllocation);
  const stockAllocation = useAppSelector(selectStockAllocation);

  return {
    isDemo,
    holdings,
    marketValue,
    totalInvested,
    unrealizedPnl,
    unrealizedPnlPct,
    todayPnl,
    todayPnlPct,
    netWorth,
    sectorAllocation,
    stockAllocation,
  };
}

/** Local dashboard data: the finance and portfolio numbers the dashboard
 * shows, watchlist symbols, and the top savings goals. */
export function useDashboardData() {
  const { isDemo, summary, spending, goals, lastMonth } = useFinanceData();
  const portfolio = usePortfolioData();
  const watchlistSymbols = useAppSelector(selectWatchlistSymbols);

  const monthlySpendingDeltaPct =
    lastMonth.expense > 0
      ? Math.round(((summary.expenses - lastMonth.expense) / lastMonth.expense) * 100)
      : 0;

  return {
    isDemo,
    netWorth: portfolio.netWorth,
    portfolioValue: portfolio.marketValue,
    totalInvested: portfolio.totalInvested,
    unrealizedPnlPct: portfolio.unrealizedPnlPct,
    todayPnl: portfolio.todayPnl,
    todayPnlPct: portfolio.todayPnlPct,
    monthlySpending: summary.expenses,
    monthlySpendingDeltaPct,
    spending,
    watchlistSymbols,
    goals: goals.slice(0, 3),
  };
}
