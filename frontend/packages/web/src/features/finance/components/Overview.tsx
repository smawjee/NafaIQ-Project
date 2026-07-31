import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, ArrowDownRight, PiggyBank, Percent } from "lucide-react";
import { AnimatedBar } from "@/components/shared/CountUpNumber";
import { IncomeExpenseChart, Sparkline } from "@/components/charts/charts";
import { formatPKR, formatSignedPKR } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useAuth } from "@/hooks/use-auth";
import { useDemo } from "@/hooks/use-demo";
import { useFinanceData } from "@/hooks/use-demo-data";
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useIncomeExpenseSeries } from "@/hooks/use-finance-series";
import { useCountUp, emptyIncomeExpenseSeries } from "@/features/finance/finance.utils";

/* ---------- glass KPI card ---------- */
function KpiCard({
  index = 0,
  accent,
  children,
}: {
  index?: number;
  accent: string;
  children: React.ReactNode;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.4, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
      whileHover={reduce ? undefined : { y: -2 }}
      className="group relative flex flex-col justify-between overflow-hidden rounded-[14px] border border-border bg-surface p-6 transition-colors duration-200 hover:border-border-hover"
    >
      {/* accent glow on hover */}
      <div
        className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-60"
        style={{ background: accent }}
      />
      <div className="relative z-10 flex h-full flex-col">{children}</div>
    </motion.div>
  );
}

function KpiLabel({ children }: { children: React.ReactNode }) {
  const { t } = useLang();
  return (
    <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-text-muted">
      {typeof children === "string" ? t(children) : children}
    </div>
  );
}

export function Overview() {
  const { t } = useLang();
  const { user } = useAuth();
  const { isDemo } = useDemo();
  const realUserEnabled = !!user && !isDemo;
  const { data: summary } = useFinanceSummary(undefined, realUserEnabled);
  const { data: seriesData } = useIncomeExpenseSeries(6, realUserEnabled);
  // Demo/local numbers come from the global Redux store so demo transactions
  // move the Overview KPIs and chart.
  const local = useFinanceData();
  const hasSeries = realUserEnabled && !!seriesData && seriesData.series.length > 0;
  const useShowcaseFinance = isDemo;

  // "income" = earned from transactions (variable); "total income" adds the
  // fixed monthly salary set in Settings, which the backend counts every month.
  const variableIncome = useShowcaseFinance ? local.summary.income : (summary?.income ?? 0);
  const fixedIncomeVal = useShowcaseFinance ? 0 : (summary?.fixed_income ?? 0);
  const incomeVal = useShowcaseFinance
    ? local.summary.income
    : (summary?.total_income ?? variableIncome);
  const expensesVal = useShowcaseFinance ? local.summary.expenses : (summary?.expenses ?? 0);
  const savingsVal = useShowcaseFinance ? local.summary.savings : (summary?.savings ?? 0);
  const rateVal = useShowcaseFinance ? local.summary.savingsRate : (summary?.savings_rate ?? 0);
  const lastIncomeVal = useShowcaseFinance
    ? local.lastMonth.income
    : (summary?.last_month_income ?? 0);
  const lastExpenseVal = useShowcaseFinance
    ? local.lastMonth.expense
    : (summary?.last_month_expense ?? 0);
  const lastSavingsVal = useShowcaseFinance
    ? local.lastMonth.income - local.lastMonth.expense
    : (summary?.last_month_savings ?? 0);
  const incomeDelta = incomeVal - lastIncomeVal;
  const expenseDeltaPct =
    lastExpenseVal > 0 ? ((expensesVal - lastExpenseVal) / lastExpenseVal) * 100 : 0;
  const savingsDelta = savingsVal - lastSavingsVal;
  const maxKpiValue = Math.max(incomeVal, expensesVal, Math.abs(savingsVal), 1);
  const incomeBar = Math.min((incomeVal / maxKpiValue) * 100, 100);
  const expenseBar = Math.min((expensesVal / maxKpiValue) * 100, 100);
  const savingsBar = Math.min((Math.max(savingsVal, 0) / maxKpiValue) * 100, 100);
  const savingsRateBar = Math.max(0, Math.min(rateVal, 100));
  const savingsRateStatus =
    rateVal >= 50
      ? "Excellent"
      : rateVal >= 20
        ? "Healthy"
        : rateVal > 0
          ? "Needs attention"
          : "No savings yet";

  const income = useCountUp(incomeVal);
  const expenses = useCountUp(expensesVal);
  const savings = useCountUp(savingsVal);
  const rate = useCountUp(rateVal, 1);

  const incomeSpark = hasSeries
    ? seriesData.series.slice(-3).map((s) => s.income)
    : !useShowcaseFinance
      ? [0, 0, 0]
      : local.series.slice(-3).map((s) => s.income);
  const expenseSpark = hasSeries
    ? seriesData.series.slice(-3).map((s) => s.expense)
    : !useShowcaseFinance
      ? [0, 0, 0]
      : local.series.slice(-3).map((s) => s.expense);

  const chartData = hasSeries
    ? seriesData.series.map((s) => ({ month: s.month, income: s.income, expense: s.expense }))
    : !useShowcaseFinance
      ? emptyIncomeExpenseSeries(6)
      : local.series;

  const totalIncome = hasSeries
    ? Math.round(seriesData.series.reduce((a, b) => a + b.income, 0))
    : !useShowcaseFinance
      ? 0
      : Math.round(local.series.reduce((a, b) => a + b.income, 0));
  const totalExpense = hasSeries
    ? Math.round(seriesData.series.reduce((a, b) => a + b.expense, 0))
    : !useShowcaseFinance
      ? 0
      : Math.round(local.series.reduce((a, b) => a + b.expense, 0));
  const totalSavings = totalIncome - totalExpense;

  return (
    <div className="relative space-y-4">
      {/* ambient background glows */}
      <div className="pointer-events-none absolute -right-16 -top-10 h-64 w-64 rounded-full bg-ai/10 blur-[100px]" />
      <div className="pointer-events-none absolute -left-16 top-1/2 h-64 w-64 rounded-full bg-bull/5 blur-[100px]" />

      <div className="relative z-10 grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        {/* Monthly Income */}
        <KpiCard index={0} accent="rgba(0,212,170,0.5)">
          <div className="badge-positive mb-4 flex h-9 w-9 items-center justify-center rounded-[10px]">
            <ArrowUpRight className="h-5 w-5 text-bull" />
          </div>
          <KpiLabel>Total Monthly Income</KpiLabel>
          <div
            dir="ltr"
            className="mt-1 font-mono text-lg font-semibold tracking-tight text-bull tabular-nums sm:text-xl"
          >
            PKR <span ref={income.ref}>{income.formatted}</span>
          </div>
          {fixedIncomeVal > 0 && (
            <div dir="ltr" className="mt-1 text-[10px] text-text-muted sm:text-[11px]">
              {formatPKR(variableIncome)} {t("earned")} + {formatPKR(fixedIncomeVal)} {t("salary")}
            </div>
          )}
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <AnimatedBar value={incomeBar} className="bg-bull" />
          </div>
          <div className="mt-3 flex items-end justify-between gap-2">
            <span
              dir="ltr"
              className={cn(
                "text-[10px] sm:text-[11px]",
                incomeDelta >= 0 ? "text-bull/80" : "text-bear/90",
              )}
            >
              {formatSignedPKR(incomeDelta)} {t("vs last month")}
            </span>
            <div className="w-14 shrink-0">
              <Sparkline data={incomeSpark} color="#00d4aa" />
            </div>
          </div>
        </KpiCard>

        {/* Total Expenses */}
        <KpiCard index={1} accent="rgba(229,72,77,0.45)">
          <div className="badge-negative mb-4 flex h-9 w-9 items-center justify-center rounded-[10px]">
            <ArrowDownRight className="h-5 w-5 text-bear" />
          </div>
          <KpiLabel>Total Expenses</KpiLabel>
          <div
            dir="ltr"
            className="mt-1 font-mono text-lg font-semibold tracking-tight text-bear tabular-nums sm:text-xl"
          >
            PKR <span ref={expenses.ref}>{expenses.formatted}</span>
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <AnimatedBar value={expenseBar} className="bg-bear" />
          </div>
          <div className="mt-3 flex items-end justify-between gap-2">
            <span
              dir="ltr"
              className={cn(
                "text-[10px] sm:text-[11px]",
                expenseDeltaPct <= 0 ? "text-bull/80" : "text-bear/90",
              )}
            >
              {expenseDeltaPct >= 0 ? "+" : ""}
              {expenseDeltaPct.toFixed(1)}% {t("vs last month")}
            </span>
            <div className="w-14 shrink-0">
              <Sparkline data={expenseSpark} color="#e5484d" />
            </div>
          </div>
        </KpiCard>

        {/* Net Savings */}
        <KpiCard index={2} accent="rgba(139,92,246,0.45)">
          <div className="badge-neutral mb-4 flex h-9 w-9 items-center justify-center rounded-[10px]">
            <PiggyBank className="h-5 w-5 text-ai" />
          </div>
          <KpiLabel>Net Savings</KpiLabel>
          <div
            dir="ltr"
            className="kpi-value-neutral mt-1 font-mono text-lg font-semibold tracking-tight text-ai tabular-nums sm:text-xl"
          >
            PKR <span ref={savings.ref}>{savings.formatted}</span>
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <AnimatedBar value={savingsBar} className="bg-ai" />
          </div>
          <div className="mt-3 flex items-center justify-between gap-2">
            <span className="text-[10px] text-text-muted sm:text-[11px]">
              {t("Saved this month")}
            </span>
            <span
              dir="ltr"
              className={cn(
                "text-[10px] sm:text-[11px]",
                savingsDelta >= 0 ? "text-bull/80" : "text-bear/90",
              )}
            >
              {formatSignedPKR(savingsDelta)}
            </span>
          </div>
        </KpiCard>

        {/* Savings Rate */}
        <KpiCard index={3} accent="rgba(245,158,11,0.45)">
          <div className="badge-neutral mb-4 flex h-9 w-9 items-center justify-center rounded-[10px]">
            <Percent className="h-5 w-5 text-warning" />
          </div>
          <KpiLabel>Savings Rate</KpiLabel>
          <div
            dir="ltr"
            className="kpi-value-neutral mt-1 font-mono text-lg font-semibold tracking-tight text-warning tabular-nums sm:text-xl"
          >
            <span ref={rate.ref}>{rate.formatted}</span>%
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <motion.div
              className="h-full rounded-full bg-warning"
              initial={{ width: 0 }}
              whileInView={{ width: `${savingsRateBar}%` }}
              viewport={{ once: true }}
              transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
          <div className="mt-2.5 flex items-center justify-between gap-2">
            <span
              className="rounded-full border border-warning/30 px-2 py-0.5 text-[10px] font-semibold text-warning"
              style={{ background: "rgba(245,158,11,0.1)" }}
            >
              {t(savingsRateStatus)}
            </span>
            <span className="text-[10px] text-text-muted sm:text-[11px]">
              {useShowcaseFinance ? t("Goal: 65%") : `${t("Goal")}: 65%`}
            </span>
          </div>
        </KpiCard>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 overflow-hidden rounded-3xl border border-white/10 bg-surface/60 p-5 backdrop-blur-xl sm:p-6"
      >
        <div className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-br from-white/[0.04] to-transparent" />
        <div className="relative z-10 flex items-end justify-between">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-text-secondary">
              {t("6-Month Overview")}
            </div>
            <div className="mt-0.5 text-[11px] text-text-muted">Jan 2026 — Jun 2026</div>
          </div>
          <div className="flex items-center gap-3 text-[11px] font-medium text-text-secondary">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-bull" />
              {t("In")}
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-bear" />
              {t("Out")}
            </span>
          </div>
        </div>
        <div className="relative z-10 mt-4">
          <IncomeExpenseChart data={chartData} />
        </div>
        <div dir="ltr" className="relative z-10 mt-3 text-center text-[11px] text-text-muted">
          {t("6-month totals")}: {t("Income")} {formatPKR(totalIncome)} · {t("Expenses")}{" "}
          {formatPKR(totalExpense)} · {t("Saved")} {formatPKR(totalSavings)}
        </div>
      </motion.div>
    </div>
  );
}
