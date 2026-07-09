import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import {
  Sparkles,
  ArrowRight,
  Plus,
  TrendingUp,
  Calendar,
  Wallet,
  Target,
} from "lucide-react";
import { toast } from "sonner";
import { Card, StatCard } from "@/components/shared/Card";
import { Change } from "@/components/charts/Change";
import { SignalBadge } from "@/components/charts/SignalBadge";
import { EmojiIcon } from "@/components/icons/icons";
import { DonutChart, PortfolioAreaChart, Sparkline, DONUT_LIGHT_PALETTE } from "@/components/charts/charts";
import { CountUpNumber, AnimatedBar } from "@/components/charts/CountUpNumber";
import { Typewriter } from "@/components/shared/Typewriter";
import { useTheme } from "@/hooks/use-theme";
import { STOCKS, WATCHLIST, generateOHLCV, fmtPKR, fmtNum } from "@/lib/data";
import { SPENDING, GOALS, BUDGETS, BILLS } from "@/lib/finance/data";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useLang, localizeDigits } from "@/hooks/use-lang";
import { useAppDispatch } from "@/store/hooks";
import { addTransaction } from "@/store/finance";
import { addHolding } from "@/store/portfolio";
import { addAlert } from "@/store/alerts";
import { usePortfolioList, useAddHolding, useCreatePortfolio, usePortfolioHistory, usePortfolioNetworth } from "@/hooks/use-portfolio";
import { useCreateUserAlert } from "@/hooks/use-alerts";
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useFinanceGoals } from "@/hooks/use-finance-goals";
import { useCreateTransaction } from "@/hooks/use-finance-transactions";
import { useSpendingByCategory } from "@/hooks/use-finance-series";
import { useWatchlist } from "@/hooks/psx/use-watchlist";
import { usePsxIndexData } from "@/hooks/psx/use-psx";
import { Modal, fieldClass } from "@/components/shared/Modal";
import { Checkbox } from "@/components/ui/checkbox";

export const Route = createFileRoute("/app")({
  head: () => ({
    meta: [
      { title: "Dashboard — NafaIQ" },
      {
        name: "description",
        content: "Your net worth, portfolio, spending and PSX signals at a glance.",
      },
    ],
  }),
  component: Dashboard,
});

const RANGES = ["1M", "3M", "6M", "1Y"] as const;

function portfolioSeries(months: number) {
  const base = 858054 / 1.1273;
  const out = [];
  const labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"].slice(6 - months);
  for (let i = 0; i < labels.length; i++) {
    const f = i / (labels.length - 1 || 1);
    out.push({
      label: labels[i],
      value: Math.round(base * (1 + 0.1273 * f + Math.sin(i) * 0.01)),
      benchmark: Math.round(base * (1 + 0.095 * f + Math.cos(i) * 0.008)),
    });
  }
  return out;
}

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function formatToday() {
  const d = new Date();
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function latestIndexChangePct(
  bars: { date: string; close: number }[] | undefined,
): number | null {
  if (!bars || bars.length < 2) return null;
  const sorted = bars.slice().sort((a, b) => a.date.localeCompare(b.date));
  const latest = sorted[sorted.length - 1];
  const previous = sorted[sorted.length - 2];
  if (!latest || !previous || previous.close === 0) return null;
  return ((latest.close - previous.close) / previous.close) * 100;
}

function Dashboard() {
  const { profile, user } = useAuth();
  const { isDemo } = useDemo();
  const { t } = useLang();
  const { theme } = useTheme();
  const useShowcaseDashboard = isDemo;
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
  const { data: portfolioHistory, isLoading: portfolioHistoryLoading } = usePortfolioHistory(historyDays, realUserEnabled);
  const { data: financeSummary } = useFinanceSummary(undefined, realUserEnabled);
  const { data: spendingByCat, isLoading: spendingByCatLoading } = useSpendingByCategory(30, realUserEnabled);
  const { data: userGoals } = useFinanceGoals(realUserEnabled);
  const { symbols: userWatchlist } = useWatchlist();
  const { data: kse100Bars } = usePsxIndexData("KSE100");
  const kse100ChangePct = latestIndexChangePct(kse100Bars);
  const kse100ChangeLabel =
    kse100ChangePct == null
      ? "--"
      : `${kse100ChangePct >= 0 ? "+" : ""}${kse100ChangePct.toFixed(2)}%`;
  const portfolioChartData = !useShowcaseDashboard
    ? (portfolioHistory?.points ?? [])
    : portfolioSeries(months);
  const dashboardWatchlist = useShowcaseDashboard ? WATCHLIST : userWatchlist;
  const dashboardGoals = !useShowcaseDashboard
    ? (userGoals ?? []).slice(0, 3).map((g) => ({
        emoji: g.emoji || "",
        name: g.name,
        saved: g.saved,
        target: g.target,
        color: (g.color === "warning" ? "warning" : "bull") as "warning" | "bull",
        ai: g.ai_tip || "",
      }))
    : GOALS.slice(0, 3);

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

      {/* AI Insight — premium recommendation widget */}
      {showAI && (
        <div className="rounded-[14px] border border-white/[0.06] bg-surface p-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-start">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Sparkles className="h-[18px] w-[18px] text-primary" strokeWidth={1.75} />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2.5">
                <h2 className="text-sm font-semibold text-text-primary">{t("AI Recommendation")}</h2>
                <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                  92% confidence
                </span>
              </div>
              <p className="mt-1.5 text-[13px] font-medium text-text-primary">
                {t("Redirect PKR 5,000 from dining to your Hajj Fund.")}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                <Typewriter
                  id="dashboard-ai-recommendation"
                  text={t(
                    "You spent 15% more on dining this month — reallocating brings your goal 3 months closer. HBL is also flashing a Strong Buy, up 2.41% on rising volume.",
                  )}
                />
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Link
                to="/psx"
                className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition hover:brightness-110"
              >
                {t("View")}
              </Link>
              <button
                onClick={() => setShowAI(false)}
                className="rounded-lg px-3 py-1.5 text-xs text-text-muted transition hover:bg-white/[0.04] hover:text-text-primary"
              >
                {t("Dismiss")}
              </button>
            </div>
          </div>
        </div>
      )}

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
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-6">
          <div className="text-[13px] font-medium text-text-secondary">{t("Total Net Worth")}</div>
          <div className="mt-3 font-mono text-4xl font-bold tabular-nums text-text-primary">
            <CountUpNumber value={useShowcaseDashboard ? 4280500 : (networth?.total_market_value ?? 0)} prefix="PKR " />
          </div>
          <div className="mt-2 font-mono text-sm tabular-nums text-bull">
            {!useShowcaseDashboard
              ? `${(networth?.today_pnl ?? 0) >= 0 ? "+" : ""}PKR ${Math.round(networth?.today_pnl ?? 0).toLocaleString()} (${(networth?.today_pnl_pct ?? 0) >= 0 ? "+" : ""}${networth?.today_pnl_pct ?? 0}%) today`
              : "+PKR 56,000 (+1.32%) this month"}
          </div>
        </Card>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 lg:col-span-6">
          <StatCard
            label="Portfolio Value"
            value={<CountUpNumber value={useShowcaseDashboard ? 858054 : (networth?.total_market_value ?? 0)} prefix="PKR " />}
            sub={!useShowcaseDashboard && networth ? `${networth.total_unrealized_pnl_pct >= 0 ? "+" : ""}${networth.total_unrealized_pnl_pct}% all time` : !useShowcaseDashboard ? "0% all time" : "+12.73% YTD"}
            subColor="text-bull"
          />
          <StatCard
            label="Monthly Spending"
            value={<CountUpNumber value={useShowcaseDashboard ? 112050 : (financeSummary?.expenses ?? 0)} prefix="PKR " />}
            sub={!useShowcaseDashboard && financeSummary && financeSummary.last_month_expense > 0
              ? `${Math.round(((financeSummary.expenses - financeSummary.last_month_expense) / financeSummary.last_month_expense) * 100)}% vs last month`
              : !useShowcaseDashboard ? "0% vs last month" : "-12% vs May"}
            subColor="text-bull"
          />
          <StatCard
            label="Today's PSX P/L"
            value={<CountUpNumber value={useShowcaseDashboard ? 17480 : Math.round(networth?.today_pnl ?? 0)} prefix={useShowcaseDashboard ? "+" : ((networth?.today_pnl ?? 0) >= 0 ? "+" : "")} />}
            sub={!useShowcaseDashboard && networth ? `${networth.today_pnl_pct >= 0 ? "+" : ""}${networth.today_pnl_pct}%` : !useShowcaseDashboard ? "0%" : "+1.42%"}
            subColor="text-bull"
          />
        </div>
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
          <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Spending Breakdown")}</h3>
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
              <DonutChart data={SPENDING} centerValue={localizeDigits("132,000")} centerLabel="PKR total" />
              <div className="mt-2 grid grid-cols-2 gap-1.5 text-xs">
                {SPENDING.map((s, i) => (
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

      {/* Watchlist strip */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-text-primary">{t("Watchlist")}</h3>
        {!useShowcaseDashboard && dashboardWatchlist.length === 0 ? (
          <Card hover={false} className="text-sm text-text-secondary">
            {t("Your watchlist is empty. Add stocks from the PSX page to track them here.")}
          </Card>
        ) : (
          <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1">
            {dashboardWatchlist.map((tk) => {
            const s = STOCKS[tk];
            if (!s) return null;
            const spark = generateOHLCV(s.seed, s.start, s.price, 7).map((c) => c.close);
            return (
              <Link
                to="/psx"
                key={tk}
                className="w-[160px] shrink-0 rounded-[8px] border border-border bg-surface p-3 transition hover:border-border-hover"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-text-primary">{tk}</span>
                  <Change pct={s.changePct} pill />
                </div>
                <div className="truncate text-[10px] text-text-muted">{t(s.name)}</div>
                <div className="mt-1 font-mono text-lg font-bold tabular-nums text-text-primary">
                  {fmtNum(s.price)}
                </div>
                <div className="my-1">
                  <Sparkline data={spark} color={s.changePct >= 0 ? "#00d4aa" : "#e5484d"} />
                </div>
                <SignalBadge signal={s.signal} />
              </Link>
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

/* ---------- Quick-Add Transaction Modal ---------- */
const TX_CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Shopping",
  "Subscriptions",
  "Savings",
  "Income",
];
const TX_ACCOUNTS = ["HBL Current", "Meezan Debit", "Easypaisa", "Meezan Savings"];

function QuickAddTransactionModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const createTransaction = useCreateTransaction();
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(TX_CATEGORIES[0]);
  const [account, setAccount] = useState(TX_ACCOUNTS[0]);
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    const num = Number(amount);
    if (!merchant.trim()) return setErr(t("Please enter a merchant name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(t("Please enter a valid amount."));
    try {
      if (user && !isDemo) {
        await createTransaction.mutateAsync({
          merchant: merchant.trim(),
          category: kind === "income" ? "Income" : category,
          source: account,
          amount: num,
          transaction_type: kind,
          transaction_date: new Date().toISOString(),
        });
      } else {
        dispatch(addTransaction({
          merchant: merchant.trim(),
          category: kind === "income" ? "Income" : category,
          account,
          amount: kind === "income" ? num : -num,
        }));
      }
      toast.success(t("Transaction added"));
      setMerchant("");
      setAmount("");
      setKind("expense");
      setCategory(TX_CATEGORIES[0]);
      onClose();
    } catch (error) {
      console.error("Add transaction error:", error);
      setErr(t("Failed to add transaction."));
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t("Add Transaction")}>
      <div className="space-y-3">
        <div className="flex gap-2">
          {(["expense", "income"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setKind(k)}
              className={cn(
                "flex-1 rounded-[6px] border py-2 text-sm font-medium capitalize transition",
                kind === k
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-text-secondary",
              )}
            >
              {t(k === "expense" ? "Expense" : "Income")}
            </button>
          ))}
        </div>
        <input
          value={merchant}
          onChange={(e) => setMerchant(e.target.value)}
          placeholder={t("Merchant / description")}
          className={fieldClass}
        />
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          inputMode="decimal"
          placeholder={t("Amount (PKR)")}
          className={fieldClass}
        />
        {kind === "expense" && (
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={fieldClass}
          >
            {TX_CATEGORIES.filter((c) => c !== "Income").map((c) => (
              <option key={c} value={c}>
                {t(c)}
              </option>
            ))}
          </select>
        )}
        <select value={account} onChange={(e) => setAccount(e.target.value)} className={fieldClass}>
          {TX_ACCOUNTS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          onClick={submit}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Add Transaction")}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- Quick-Add Holding Modal ---------- */
function QuickAddHoldingModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const isLoggedIn = !!user && !isDemo;
  const { data: portfolios } = usePortfolioList(isLoggedIn);
  const portfolioId = portfolios?.[0]?.id ?? null;
  const addHoldingApi = useAddHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();
  const [ticker, setTicker] = useState("");
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [err, setErr] = useState("");

  function computeSignal(sym: string, cur: number, cost: number) {
    const stock = STOCKS[sym.toUpperCase()];
    if (stock) return stock.signal;
    const gainPct = ((cur - cost) / cost) * 100;
    if (gainPct >= 15) return "STRONG BUY";
    if (gainPct >= 5) return "BUY";
    if (gainPct >= -5) return "HOLD";
    if (gainPct >= -15) return "SELL";
    return "STRONG SELL";
  }

  const submit = () => {
    setErr("");
    const s = Number(shares);
    const ac = Number(avgCost);
    if (!ticker.trim()) return setErr(t("Please enter a stock symbol."));
    if (!shares || Number.isNaN(s) || s <= 0)
      return setErr(t("Please enter a valid number of shares."));
    if (!avgCost || Number.isNaN(ac) || ac <= 0)
      return setErr(t("Please enter a valid buy price."));
    const sym = ticker.trim().toUpperCase();
    const stock = STOCKS[sym];
    const cur = stock?.price ?? ac;
    if (isLoggedIn) {
      const doAdd = (pid: number) => {
        addHoldingApi.mutate(
          { symbol: sym, shares: s, avg_cost: ac },
          {
            onSuccess: () => {
              toast.success(t("Holding added"));
              setTicker("");
              setShares("");
              setAvgCost("");
              onClose();
            },
          },
        );
      };
      if (portfolioId) {
        doAdd(portfolioId);
      } else {
        createPortfolio.mutate("Main", { onSuccess: (p) => doAdd(p.id) });
      }
    } else {
      dispatch(addHolding({
        ticker: sym,
        sector: stock?.sector ?? "—",
        shares: s,
        avgCost: ac,
        current: cur,
        signal: computeSignal(sym, cur, ac),
      }));
      toast.success(t("Holding added"));
      setTicker("");
      setShares("");
      setAvgCost("");
      onClose();
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t("Add Holding")}>
      <div className="space-y-3">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder={t("Stock symbol (e.g. HBL)")}
          className={fieldClass}
        />
        <input
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          inputMode="decimal"
          placeholder={t("Shares")}
          className={fieldClass}
        />
        <input
          value={avgCost}
          onChange={(e) => setAvgCost(e.target.value)}
          inputMode="decimal"
          placeholder={t("Buy price (PKR)")}
          className={fieldClass}
        />
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          onClick={submit}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Add Holding")}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- Quick-Add Alert Modal ---------- */
const ALERT_TYPES = [
  { label: "Stock Price", icon: TrendingUp, emoji: "🔔" },
  { label: "Bill Reminder", icon: Calendar, emoji: "📅" },
  { label: "Budget", icon: Wallet, emoji: "💸" },
  { label: "Goal Milestone", icon: Target, emoji: "🎯" },
];
const ALERT_STOCKS = ["HBL", "ENGRO", "LUCK", "OGDC"];

function QuickAddAlertModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const dispatch = useAppDispatch();
  const isLoggedIn = !!user && !isDemo;
  const createUserAlert = useCreateUserAlert();
  const [type, setType] = useState("Stock Price");
  const [stock, setStock] = useState(ALERT_STOCKS[0]);
  const [direction, setDirection] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState(BILLS[0]?.name ?? "");
  const [timing, setTiming] = useState("1 day before");
  const [budgetCat, setBudgetCat] = useState(BUDGETS[0]?.category ?? "");
  const [budgetThreshold, setBudgetThreshold] = useState("80");
  const [goal, setGoal] = useState(GOALS[0]?.name ?? "");
  const [goalMilestone, setGoalMilestone] = useState("50");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [err, setErr] = useState("");

  const submit = () => {
    setErr("");
    const ty = ALERT_TYPES.find((x) => x.label === type)!;
    let title = "";
    let meta: string | Record<string, unknown> = "";

    if (type === "Stock Price") {
      const num = Number(price);
      if (!price || Number.isNaN(num) || num <= 0) {
        setErr(t("Please enter a valid price."));
        return;
      }
      title = `${stock} ${direction.toLowerCase()} PKR ${num}`;
      meta = isLoggedIn ? { symbol: stock, direction: direction.toLowerCase(), price: num } : `Created ${new Date().toLocaleString("en-US", { month: "short", day: "numeric" })}`;
    } else if (type === "Bill Reminder") {
      title = `${bill} — ${timing}`;
      meta = isLoggedIn ? { bill, timing } : "Recurring monthly";
    } else if (type === "Budget") {
      if (!budgetCat) { setErr(t("Please select a budget category.")); return; }
      title = `${budgetCat} at ${budgetThreshold}% of budget`;
      meta = isLoggedIn ? { category: budgetCat, threshold: budgetThreshold } : "Monthly";
    } else {
      if (!goal) { setErr(t("Please select a goal.")); return; }
      title = `${goal} ${goalMilestone}% reached`;
      meta = isLoggedIn ? { goal, milestone: goalMilestone } : "One-time";
    }

    if (isLoggedIn) {
      createUserAlert.mutate(
        {
          type: type === "Stock Price" ? "stock_price" : type === "Bill Reminder" ? "bill" : type === "Budget" ? "budget" : "goal",
          title,
          meta: typeof meta === "object" ? meta : {},
        },
        {
          onSuccess: () => {
            toast.success(t("Alert created"));
            setPrice("");
            setBudgetThreshold("80");
            setGoalMilestone("50");
            setErr("");
            onClose();
          },
        },
      );
    } else {
      const channels = [push && "Push", email && "Email"].filter(Boolean).join(" + ") || "In-app";
      dispatch(addAlert({
        alert: { emoji: ty.emoji, title, type: `${type} Alert`, meta: typeof meta === "string" ? meta : JSON.stringify(meta), on: true },
        notifMsg: `New alert created: ${title} (${channels})`,
      }));
      toast.success(t("Alert created"));
      setPrice("");
      setBudgetThreshold("80");
      setGoalMilestone("50");
      setErr("");
      onClose();
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={t("Add Alert")}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {ALERT_TYPES.map((ty) => (
            <button
              key={ty.label}
              onClick={() => setType(ty.label)}
              className={cn(
                "flex flex-col items-center gap-1.5 rounded-[10px] border p-3 text-xs font-medium transition",
                type === ty.label
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-white/[0.06] text-text-secondary hover:bg-white/[0.04]",
              )}
            >
              <ty.icon className="h-5 w-5" strokeWidth={1.75} />
              {t(ty.label)}
            </button>
          ))}
        </div>
        {type === "Stock Price" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={stock}
              onChange={(e) => setStock(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {ALERT_STOCKS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value)}
                className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
              >
                <option value="Above">{t("Above")}</option>
                <option value="Below">{t("Below")}</option>
              </select>
              <input
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                inputMode="decimal"
                placeholder={t("Price")}
                className="w-full rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted"
              />
            </div>
          </div>
        ) : type === "Bill Reminder" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={bill}
              onChange={(e) => setBill(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {BILLS.map((b) => (
                <option key={b.name} value={b.name}>{b.name}</option>
              ))}
            </select>
            <select
              value={timing}
              onChange={(e) => setTiming(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              <option>{t("1 day before")}</option>
              <option>{t("3 days before")}</option>
              <option>{t("7 days before")}</option>
            </select>
          </div>
        ) : type === "Budget" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={budgetCat}
              onChange={(e) => setBudgetCat(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {BUDGETS.map((b) => (
                <option key={b.category} value={b.category}>{t(b.category)}</option>
              ))}
            </select>
            <select
              value={budgetThreshold}
              onChange={(e) => setBudgetThreshold(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              <option value="50">{t("50%")}</option>
              <option value="75">{t("75%")}</option>
              <option value="80">{t("80%")}</option>
              <option value="90">{t("90%")}</option>
              <option value="100">{t("100%")}</option>
            </select>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              {GOALS.map((g) => (
                <option key={g.name} value={g.name}>{g.emoji} {t(g.name)}</option>
              ))}
            </select>
            <select
              value={goalMilestone}
              onChange={(e) => setGoalMilestone(e.target.value)}
              className="rounded-[6px] border border-border bg-elevated px-3 py-2 text-sm text-text-primary"
            >
              <option value="25">{t("25%")}</option>
              <option value="50">{t("50%")}</option>
              <option value="75">{t("75%")}</option>
              <option value="90">{t("90%")}</option>
              <option value="100">{t("100%")}</option>
            </select>
          </div>
        )}
        <div className="flex flex-wrap gap-3 text-xs text-text-secondary">
          <label className="flex items-center gap-1.5">
            <Checkbox checked={push} onCheckedChange={(c) => setPush(c === true)} />
            {t("Push")}
          </label>
          <label className="flex items-center gap-1.5">
            <Checkbox checked={email} onCheckedChange={(c) => setEmail(c === true)} />
            {t("Email")}
          </label>
        </div>
        {err && <div className="text-xs text-bear">{err}</div>}
        <button
          onClick={submit}
          className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
        >
          {t("Create Alert")}
        </button>
      </div>
    </Modal>
  );
}
