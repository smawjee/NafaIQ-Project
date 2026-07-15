import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { TrendingUp, Wallet, Coins, CreditCard, Activity, X } from "lucide-react";
import { toast } from "sonner";
import { Card, StatCard } from "@/components/shared/Card";
import { Change } from "@/components/market/Change";
import { EmojiIcon } from "@/components/icons/icons";
import { DonutChart, PortfolioAreaChart, DONUT_LIGHT_PALETTE } from "@/components/charts/charts";
import { CountUpNumber, AnimatedBar } from "@/components/shared/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { useTheme } from "@/hooks/use-theme";
import { STOCKS, fmtPKR, fmtNum } from "@/lib/data";
import { formatSignedPKR } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLang, localizeDigits } from "@/hooks/use-lang";
import { useDashboardData } from "@/hooks/use-demo-data";
import { usePortfolioHistory, usePortfolioNetworth } from "@/hooks/use-portfolio";
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
import { useSpendingByCategory } from "@/hooks/use-finance-series";
import {
  useWatchlist,
  useEnrichedWatchlist,
  type EnrichedWatchlistItem,
} from "@/hooks/psx/use-watchlist";
import { StockLogo } from "@/components/search/StockLogo";
import { logoUrlFor } from "@/lib/psx/stock-search";
import { usePsxIndexCards } from "@/hooks/psx/use-psx";
import { RANGES } from "@/features/dashboard/dashboard.data";
import { portfolioSeries, formatToday } from "@/features/dashboard/dashboard.utils";
import { QuickAddTransactionModal } from "@/features/dashboard/components/QuickAddTransactionModal";
import { QuickAddHoldingModal } from "@/features/dashboard/components/QuickAddHoldingModal";
import { QuickAddAlertModal } from "@/features/dashboard/components/QuickAddAlertModal";
import { DashboardRecommendation } from "@/features/dashboard/components/DashboardRecommendation";
import { MacroWidget } from "@/features/dashboard/MacroWidget";
import { UnusualActivityWidget } from "@/features/psx/UnusualActivityWidget";
import { NewsFeed } from "@/features/psx/NewsFeed";

export function Dashboard() {
  const { profile, user } = useAuth();
  const { isDemo } = useDemo();
  const { t } = useLang();
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
  const dashboardGoals = !useShowcaseDashboard
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
  const pctLabel = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      {/* Greeting — compact hero */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-bold text-text-primary sm:text-2xl">
            {t("Asalam-o-Alaikum,")} {t(firstName)}
          </h1>
          <p className="mt-0.5 text-[13px] text-text-secondary">
            {formatToday()} · {t("KSE-100")}{" "}
            <span
              className={cn(
                "font-mono",
                kse100ChangePct == null
                  ? "text-text-muted"
                  : kse100ChangePct >= 0
                    ? "text-bull"
                    : "text-bear",
              )}
            >
              {localizeDigits(kse100ChangeLabel)}
            </span>{" "}
            {t("today")}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            to="/psx"
            className="rounded-lg bg-primary px-3.5 py-2 text-[13px] font-semibold text-primary-foreground transition-all duration-200 hover:-translate-y-0.5 hover:brightness-110"
          >
            {t("Explore PSX")}
          </Link>
          <button
            onClick={() => setTxOpen(true)}
            className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.16]"
          >
            {t("Add Transaction")}
          </button>
          <button
            onClick={() => setHoldingOpen(true)}
            className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.16]"
          >
            {t("Add Holding")}
          </button>
          <button
            onClick={() => setAlertOpen(true)}
            className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition-all duration-200 hover:-translate-y-0.5 hover:border-white/[0.16]"
          >
            {t("Add Alert")}
          </button>
        </div>
      </div>

      {/* AI Insight — verified cross-domain nudge (spec §3.5) */}
      <DashboardRecommendation enabled={showAI} onDismiss={() => setShowAI(false)} />

      {/* Metric cards — Net Worth primary, rest secondary */}
      {user && !isDemo && networth && networth.holding_count === 0 ? (
        <div className="rounded-[14px] border border-white/[0.06] bg-surface p-5 text-center">
          <h2 className="text-lg font-semibold text-text-primary">{t("Welcome to NafaIQ!")}</h2>
          <p className="mt-2 max-w-md mx-auto text-sm leading-relaxed text-text-secondary">
            {t("Add your first holding, transaction, or goal to get started with real insights.")}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-3">
            <button
              onClick={() => setHoldingOpen(true)}
              className="rounded-lg bg-primary px-3.5 py-2 text-[13px] font-semibold text-primary-foreground transition hover:brightness-110"
            >
              {t("Add Holding")}
            </button>
            <button
              onClick={() => setTxOpen(true)}
              className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition hover:border-white/[0.16]"
            >
              {t("Add Transaction")}
            </button>
            <Link
              to="/psx"
              className="rounded-lg border border-white/[0.08] bg-surface px-3.5 py-2 text-[13px] font-semibold text-text-primary transition hover:border-white/[0.16]"
            >
              {t("Explore PSX")}
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
          <StatCard
            variant="hero"
            className="sm:col-span-2"
            label="Total Net Worth"
            icon={Wallet}
            info="Your portfolio's market value plus cash — your total wealth on NafaIQ."
            value={<CountUpNumber value={kpiNetWorth} prefix="PKR " />}
            sub={`${formatSignedPKR(Math.round(kpiTodayPnl))} (${pctLabel(kpiTodayPnlPct)}) today`}
            trend={kpiTodayPnl >= 0 ? "up" : "down"}
          />
          <StatCard
            label="Portfolio Value"
            icon={TrendingUp}
            value={<CountUpNumber value={kpiPortfolioValue} prefix="PKR " />}
            sub={`${pctLabel(kpiUnrealizedPct)} all time`}
            trend={kpiUnrealizedPct >= 0 ? "up" : "down"}
          />
          <StatCard
            label="Total Invested"
            icon={Coins}
            info="The total cost basis of your holdings — what you originally paid for them."
            value={<CountUpNumber value={kpiTotalInvested} prefix="PKR " />}
            sub="cost basis"
            trend="neutral"
          />
          <StatCard
            label="Monthly Spending"
            icon={CreditCard}
            value={<CountUpNumber value={kpiMonthlySpending} prefix="PKR " />}
            sub={`${kpiSpendingDeltaPct >= 0 ? "+" : ""}${kpiSpendingDeltaPct}% vs last month`}
            trend={kpiSpendingDeltaPct > 0 ? "down" : "up"}
          />
          <StatCard
            label="Today's PSX P/L"
            icon={Activity}
            info="Change in your holdings' value today versus yesterday's closing prices."
            value={
              <CountUpNumber
                value={Math.abs(Math.round(kpiTodayPnl))}
                prefix={kpiTodayPnl >= 0 ? "+PKR " : "-PKR "}
              />
            }
            sub={pctLabel(kpiTodayPnlPct)}
            trend={kpiTodayPnl >= 0 ? "up" : "down"}
          />
        </div>
      )}

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">{t("Portfolio Value")}</h3>
            <div className="flex gap-1">
              {RANGES.map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={cn(
                    "rounded-[6px] px-2.5 py-1 text-xs font-medium transition",
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
          {!useShowcaseDashboard && portfolioHistoryLoading ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-text-secondary">
              {t("Loading portfolio history...")}
            </div>
          ) : !useShowcaseDashboard && portfolioChartData.length === 0 ? (
            <div className="flex h-[300px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
              {t("No portfolio history yet. Add holdings to build your chart.")}
            </div>
          ) : (
            <PortfolioAreaChart data={portfolioChartData} />
          )}
          <div className="mt-2 flex gap-4 text-xs text-text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-bull" />
              {t("Portfolio")}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 bg-text-secondary" />
              {t("KSE-100")}
            </span>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">
            {t("Spending Breakdown")}
          </h3>
          {!useShowcaseDashboard && spendingByCatLoading ? (
            <div className="flex h-[220px] items-center justify-center text-sm text-text-secondary">
              {t("Loading spending breakdown...")}
            </div>
          ) : !useShowcaseDashboard && spendingByCat && spendingByCat.categories.length > 0 ? (
            <>
              <DonutChart
                data={spendingByCat.categories.slice(0, 5).map((c, i) => ({
                  name: c.category,
                  value: c.pct,
                  amount: c.amount,
                  color: DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length],
                }))}
                centerValue={localizeDigits(Math.round(spendingByCat.total).toLocaleString())}
                centerLabel="PKR total"
              />
              <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
                {spendingByCat.categories.slice(0, 5).map((c, i) => (
                  <span key={c.category} className="flex items-center gap-1.5 text-text-secondary">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length] }}
                    />
                    {t(c.category)} {localizeDigits(`${c.pct}%`)}
                  </span>
                ))}
              </div>
            </>
          ) : !useShowcaseDashboard ? (
            <div className="flex h-[220px] items-center justify-center rounded-[8px] border border-dashed border-border text-center text-sm text-text-secondary">
              {t("No spending data yet. Add transactions to see your breakdown.")}
            </div>
          ) : (
            <>
              <DonutChart
                data={showcase.spending.categories}
                centerValue={localizeDigits(Math.round(showcase.spending.total).toLocaleString())}
                centerLabel="PKR total"
              />
              <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
                {showcase.spending.categories.map((s, i) => (
                  <span key={s.name} className="flex items-center gap-1.5 text-text-secondary">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{
                        background:
                          theme === "light"
                            ? DONUT_LIGHT_PALETTE[i % DONUT_LIGHT_PALETTE.length]
                            : s.color,
                      }}
                    />
                    {t(s.name)} {localizeDigits(`${s.value}%`)}
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* Workstream D: macro snapshot + unusual activity + latest news */}
      <div className="grid gap-4 lg:grid-cols-3">
        <MacroWidget />
        <UnusualActivityWidget />
        <NewsFeed limit={6} />
      </div>

      {/* Watchlist strip */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Watchlist")}</h3>
        {watchlistLoading ? (
          <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-[120px] w-[160px] shrink-0 animate-pulse rounded-[8px] bg-surface-hover"
              />
            ))}
          </div>
        ) : dashboardWatchlist.length === 0 ? (
          <Card hover={false} className="text-sm text-text-secondary">
            {t("Your watchlist is empty. Add stocks from the PSX page to track them here.")}
          </Card>
        ) : useShowcaseDashboard ? (
          <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
            {(dashboardWatchlist as string[]).map((tk) => {
              const s = STOCKS[tk];
              const price = s?.price ?? 0;
              const changePct = s?.changePct ?? 0;
              return (
                <div key={tk} className="group relative w-[160px] shrink-0">
                  <Link
                    to="/psx"
                    className="block rounded-[8px] border border-border bg-surface p-3 transition hover:border-border-hover"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-text-primary">{tk}</span>
                      <Change pct={changePct} pill />
                    </div>
                    <div className="truncate text-[10px] text-text-muted">{t(s?.name ?? tk)}</div>
                    <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
                      {fmtNum(price)}
                    </div>
                    <div
                      className={cn(
                        "mt-1 text-[11px] font-mono tabular-nums",
                        changePct >= 0 ? "text-bull" : "text-bear",
                      )}
                    >
                      {changePct >= 0 ? "+" : ""}
                      {changePct.toFixed(2)}%
                    </div>
                  </Link>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      removeFromWatchlist(tk);
                      toast(`${tk} ${t("removed from watchlist")}`);
                    }}
                    aria-label={`Remove ${tk} from watchlist`}
                    className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-text-muted opacity-0 transition hover:bg-surface-hover hover:text-text-primary group-hover:opacity-100"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
            {(dashboardWatchlist as EnrichedWatchlistItem[]).map((item) => {
              const hasPrice = item.price != null && item.price > 0;
              const changePct = item.change_pct ?? 0;
              return (
                <div key={item.symbol} className="group relative w-[160px] shrink-0">
                  <Link
                    to={"/stock/" + item.symbol}
                    className="block rounded-[8px] border border-border bg-surface p-3 transition hover:border-border-hover"
                  >
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-semibold text-text-primary">
                        <StockLogo
                          symbol={item.symbol}
                          logoUrl={logoUrlFor(item.logoid)}
                          size={18}
                        />
                        {item.symbol}
                      </span>
                      {hasPrice && <Change pct={changePct} pill />}
                    </div>
                    <div className="truncate text-[10px] text-text-muted">{item.company_name}</div>
                    <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
                      {hasPrice ? fmtNum(item.price as number) : "—"}
                    </div>
                    {hasPrice ? (
                      <div
                        className={cn(
                          "mt-1 text-[11px] font-mono tabular-nums",
                          changePct >= 0 ? "text-bull" : "text-bear",
                        )}
                      >
                        {changePct >= 0 ? "+" : ""}
                        {changePct.toFixed(2)}%
                      </div>
                    ) : (
                      <div className="mt-1 text-[11px] text-text-muted">
                        {t("Price unavailable")}
                      </div>
                    )}
                  </Link>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      removeFromWatchlist(item.symbol);
                      toast(`${item.symbol} ${t("removed from watchlist")}`);
                    }}
                    aria-label={`Remove ${item.symbol} from watchlist`}
                    className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-text-muted opacity-0 transition hover:bg-surface-hover hover:text-text-primary group-hover:opacity-100"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Savings goals */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Savings Goals")}</h3>
        {user && dashboardGoals.length === 0 ? (
          <Card hover={false} className="text-sm text-text-secondary">
            {t("No savings goals yet. Add a goal from Finance to track progress here.")}
          </Card>
        ) : (
          <div className="scrollbar-none flex gap-4 overflow-x-auto py-3 lg:grid lg:grid-cols-3">
            {dashboardGoals.map((g) => {
              const pct = g.target > 0 ? Math.round((g.saved / g.target) * 100) : 0;
              return (
                <Card key={g.name} className="w-[280px] shrink-0 lg:w-auto">
                  <div className="flex items-center gap-2">
                    <span className="flex h-9 w-9 items-center justify-center rounded-[8px] border border-bull/20 bg-bull/[0.08] text-bull">
                      <EmojiIcon emoji={g.emoji} size={16} />
                    </span>
                    <span className="font-semibold text-text-primary">{t(g.name)}</span>
                    <span className="ml-auto font-mono text-sm font-bold tabular-nums text-bull">
                      {pct}%
                    </span>
                  </div>
                  <div className="mt-2 font-mono text-xs tabular-nums text-text-secondary">
                    {fmtPKR(g.saved)} / {fmtPKR(g.target)}
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
                    <AnimatedBar
                      value={pct}
                      className={g.color === "bull" ? "bg-bull" : "bg-warning"}
                    />
                  </div>
                  <p className="mt-2 text-[11px] leading-relaxed text-text-muted">{t(g.ai)}</p>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <QuickAddTransactionModal open={txOpen} onClose={() => setTxOpen(false)} />
      <QuickAddHoldingModal open={holdingOpen} onClose={() => setHoldingOpen(false)} />
      <QuickAddAlertModal open={alertOpen} onClose={() => setAlertOpen(false)} />
    </div>
  );
}
