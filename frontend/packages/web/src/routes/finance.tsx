import {
  getFinanceTransactions,
  addFinanceTransaction,
  deleteFinanceTransaction,
} from "@/lib/finance/financeTransactions";

import {
  addFinanceBill,
  deleteFinanceBill,
  getFinanceBills,
  markFinanceBillPaid,
  type FinanceBill,
} from "@/lib/finance/financeBills";
import { createFileRoute } from "@tanstack/react-router";
import { useAuth } from "@/hooks/use-auth";
import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import {
  Plus,
  Search,
  Check,
  Sparkles,
  Loader2,
  X,
  ArrowUpRight,
  ArrowDownRight,
  PiggyBank,
  Percent,
  Lightbulb,
  CalendarIcon,
  Scale,
  FileDown,
  Coins,

} from "lucide-react";
import { format } from "date-fns";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { EmojiIcon } from "@/components/icons/icons";
import { Card } from "@/components/shared/Card";
import { AnimatedBar, CountUpNumber } from "@/components/charts/CountUpNumber";
import { IncomeExpenseChart, Sparkline } from "@/components/charts/charts";
import { Typewriter } from "@/components/shared/Typewriter";
import { fmtPKR } from "@/lib/data";
import { formatNumber, formatPKR, formatSignedPKR } from "@/lib/format";
import { BUDGETS, INCOME_EXPENSE, type Goal } from "@/lib/finance/data";
import { cn } from "@/lib/utils";
import { useLang } from "@/hooks/use-lang";
import { useFinanceStore, financeActions } from "@/hooks/finance/use-finance-store";
import { useFinanceSummary } from "@/hooks/use-finance-summary";
import { useFinanceBudgets, useCreateBudget, useUpdateBudget, useDeleteBudget } from "@/hooks/use-finance-budgets";
import { useFinanceGoals as useApiFinanceGoals, useCreateGoal as useApiCreateGoal, useContributeGoal as useApiContributeGoal, useDeleteGoal as useApiDeleteGoal } from "@/hooks/use-finance-goals";
import { useIncomeExpenseSeries, useSpendingByCategory } from "@/hooks/use-finance-series";
import { Modal, fieldClass } from "@/components/shared/Modal";

export const Route = createFileRoute("/finance")({
  head: () => ({
    meta: [
      { title: "Finance — NafaIQ" },
      {
        name: "description",
        content: "Track income, expenses, budgets, bills and savings goals with AI guidance.",
      },
    ],
  }),
  component: Finance,
});

const TABS = ["Overview", "Transactions", "Budgets", "Bills", "Goals", "Zakat"] as const;
type Tab = (typeof TABS)[number];

const CAT_COLOR: Record<string, string> = {
  Utilities: "#3b82f6",
  Income: "#00d4aa",
  "Food & Dining": "#f59e0b",
  Transport: "#8b5cf6",
  Groceries: "#00d4aa",
  Subscriptions: "#e5484d",
  Shopping: "#8b5cf6",
  Savings: "#6b7280",
};

function Finance() {
  const { t: tr } = useLang();
  const [tab, setTab] = useState<Tab>("Overview");
  const [reportState, setReportState] = useState<"idle" | "loading" | "open">("idle");

  function generate() {
    setReportState("loading");
    setTimeout(() => setReportState("open"), 2000);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-text-primary sm:text-3xl">
          {tr("Personal Finance")}
        </h1>
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-surface/60 backdrop-blur-md">
          <span className="h-2 w-2 animate-pulse rounded-full bg-bull" />
        </div>
      </div>
      <div className="scrollbar-none flex gap-1 overflow-x-auto rounded-[10px] border border-white/[0.06] bg-surface p-1">
        {TABS.map((tb) => (
          <button
            key={tb}
            onClick={() => setTab(tb)}
            className={cn(
              "shrink-0 rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
              tab === tb
                ? "bg-primary/10 text-primary"
                : "text-text-secondary hover:text-text-primary",
            )}
          >
            {tr(tb)}
          </button>
        ))}
      </div>

      {tab === "Overview" && <Overview />}
      {tab === "Transactions" && <Transactions />}
      {tab === "Budgets" && <Budgets />}
      {tab === "Bills" && <Bills />}
      {tab === "Goals" && <Goals />}
      {tab === "Zakat" && <Zakat />}

      {/* AI report */}
      <div className="rounded-[8px] border border-border border-l-4 border-l-ai bg-ai-tint p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <Sparkles className="h-5 w-5 shrink-0 text-ai" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-text-primary">{tr("AI Finance Report")}</h3>
            <p className="text-sm text-text-secondary">
              {tr(
                "Get a plain-English analysis — income vs expense trends, budget health, savings rate assessment, and personalized money tips.",
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
                {tr("Analyzing…")}
              </>
            ) : (
              tr("Generate Report")
            )}
          </button>
        </div>
      </div>

      {reportState === "open" && <FinanceReportModal onClose={() => setReportState("idle")} />}
    </div>
  );
}

/* ---------- count-up hook (animates a number when it scrolls into view) ---------- */
function useCountUp(target: number, decimals = 0, duration = 1200) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.4 });
  const [val, setVal] = useState(reduce ? target : 0);

  useEffect(() => {
    if (reduce) {
      setVal(target);
      return;
    }
    if (!inView) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(target * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, target, duration, reduce]);

  const formatted = formatNumber(val, decimals);
  return { ref, formatted };
}

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
      className="group relative flex flex-col justify-between overflow-hidden rounded-[14px] border border-white/[0.06] bg-surface p-6 transition-colors duration-200 hover:border-white/[0.12]"
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

function Overview() {
  const { t } = useLang();
  const { user } = useAuth();
  const { data: summary } = useFinanceSummary(undefined, !!user);
  const { data: seriesData } = useIncomeExpenseSeries(6, !!user);

  const incomeVal = user && summary ? summary.income : 47500;
  const expensesVal = user && summary ? summary.expenses : 18675;
  const savingsVal = user && summary ? summary.savings : 28825;
  const rateVal = user && summary ? summary.savings_rate : 60.7;

  const income = useCountUp(incomeVal);
  const expenses = useCountUp(expensesVal);
  const savings = useCountUp(savingsVal);
  const rate = useCountUp(rateVal, 1);

  const incomeSpark = user && seriesData && seriesData.series.length > 0
    ? seriesData.series.slice(-3).map((s) => s.income)
    : [43000, 45000, 47500];
  const expenseSpark = user && seriesData && seriesData.series.length > 0
    ? seriesData.series.slice(-3).map((s) => s.expense)
    : [22000, 21200, 18675];

  const chartData = user && seriesData && seriesData.series.length > 0
    ? seriesData.series.map((s) => ({ month: s.month, income: s.income, expense: s.expense }))
    : INCOME_EXPENSE;

  const totalIncome = user && seriesData && seriesData.series.length > 0
    ? Math.round(seriesData.series.reduce((a, b) => a + b.income, 0))
    : 285000;
  const totalExpense = user && seriesData && seriesData.series.length > 0
    ? Math.round(seriesData.series.reduce((a, b) => a + b.expense, 0))
    : 112050;
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
          <KpiLabel>Monthly Income</KpiLabel>
          <div dir="ltr" className="mt-1 font-mono text-lg font-semibold tracking-tight text-bull tabular-nums sm:text-xl">
            PKR <span ref={income.ref}>{income.formatted}</span>
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <AnimatedBar value={78} className="bg-bull" />
          </div>
          <div className="mt-3 flex items-end justify-between gap-2">
            <span dir="ltr" className="text-[10px] text-bull/80 sm:text-[11px]">
              {formatSignedPKR(2500)} {t("vs last month")}
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
          <div dir="ltr" className="mt-1 font-mono text-lg font-semibold tracking-tight text-bear tabular-nums sm:text-xl">
            PKR <span ref={expenses.ref}>{expenses.formatted}</span>
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <AnimatedBar value={40} className="bg-bear" />
          </div>
          <div className="mt-3 flex items-end justify-between gap-2">
            <span dir="ltr" className="text-[10px] text-bear/90 sm:text-[11px]">-12% {t("vs last month")}</span>
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
          <div dir="ltr" className="kpi-value-neutral mt-1 font-mono text-lg font-semibold tracking-tight text-ai tabular-nums sm:text-xl">
            PKR <span ref={savings.ref}>{savings.formatted}</span>
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <AnimatedBar value={61} className="bg-ai" />
          </div>
          <div className="mt-3 flex items-center justify-between gap-2">
            <span className="text-[10px] text-text-muted sm:text-[11px]">{t("Saved this month")}</span>
            <span dir="ltr" className="text-[10px] text-bull/80 sm:text-[11px]">{formatSignedPKR(4825)}</span>
          </div>
        </KpiCard>

        {/* Savings Rate */}
        <KpiCard index={3} accent="rgba(245,158,11,0.45)">
          <div className="badge-neutral mb-4 flex h-9 w-9 items-center justify-center rounded-[10px]">
            <Percent className="h-5 w-5 text-warning" />
          </div>
          <KpiLabel>Savings Rate</KpiLabel>
          <div dir="ltr" className="kpi-value-neutral mt-1 font-mono text-lg font-semibold tracking-tight text-warning tabular-nums sm:text-xl">
            <span ref={rate.ref}>{rate.formatted}</span>%
          </div>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/5">
            <motion.div
              className="h-full rounded-full bg-warning"
              initial={{ width: 0 }}
              whileInView={{ width: "60.7%" }}
              viewport={{ once: true }}
              transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
          <div className="mt-2.5 flex items-center justify-between gap-2">
            <span
              className="rounded-full border border-warning/30 px-2 py-0.5 text-[10px] font-semibold text-warning"
              style={{ background: "rgba(245,158,11,0.1)" }}
            >
              {t("Excellent")}
            </span>
            <span className="text-[10px] text-text-muted sm:text-[11px]">{t("Goal: 65%")}</span>
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

const CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Shopping",
  "Subscriptions",
  "Savings",
  "Income",
];
const ACCOUNTS = ["HBL Current", "Meezan Debit", "Easypaisa", "Meezan Savings"];

function Transactions() {
  const { t: tr } = useLang();
  const { user } = useAuth();

  const [transactions, setTransactions] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // add form
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [account, setAccount] = useState(ACCOUNTS[0]);
  const [err, setErr] = useState("");

  async function loadTransactions() {
    if (!user) {
      setTransactions([]);
      return;
    }

    try {
      setLoading(true);
      const data = await getFinanceTransactions(user.id);
      setTransactions(data ?? []);
    } catch (error) {
      console.error("Load transactions error:", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTransactions();
  }, [user]);

  const filtered = transactions.filter((t) => {
    const q = query.toLowerCase();
    return (
      !q ||
      t.merchant?.toLowerCase().includes(q) ||
      t.category?.toLowerCase().includes(q) ||
      t.transaction_type?.toLowerCase().includes(q) ||
      t.source?.toLowerCase().includes(q)
    );
  });

  const grouped = filtered.reduce<Record<string, typeof transactions>>((acc, t) => {
    const date = t.transaction_date
      ? new Date(t.transaction_date).toLocaleDateString("en-US", {
          month: "long",
          day: "numeric",
        })
      : "No Date";

    (acc[date] ??= []).push(t);
    return acc;
  }, {});

  const submit = async () => {
    setErr("");

    if (!user) return setErr(tr("Please log in first."));

    const num = Number(amount);

    if (!merchant.trim()) return setErr(tr("Please enter a merchant name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(tr("Please enter a valid amount."));

    try {
      await addFinanceTransaction(user.id, {
        merchant: merchant.trim(),
        amount: kind === "income" ? num : -num,
        category: kind === "income" ? "Income" : category,
        transaction_type: kind === "income" ? "Income" : "Expense",
        transaction_date: new Date().toISOString(),
        currency: "PKR",
        source: account || "manual",
        email_subject: null,
        raw_text: null,
      });

      await loadTransactions();

      setMerchant("");
      setAmount("");
      setKind("expense");
      setCategory(CATEGORIES[0]);
      setAccount(ACCOUNTS[0]);
      setOpen(false);
    } catch (error) {
      console.error("Add transaction error:", error);
      setErr(tr("Failed to add transaction."));
    }
  };

  const handleDelete = async (id: string) => {
    if (!user) return;

    const ok = confirm("Delete this transaction?");
    if (!ok) return;

    try {
      await deleteFinanceTransaction(id, user.id);
      await loadTransactions();
    } catch (error) {
      console.error("Delete transaction error:", error);
      alert("Failed to delete transaction.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <div className="flex flex-1 items-center gap-2 rounded-[6px] border border-border bg-surface px-3 py-2">
          <Search className="h-4 w-4 text-text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={tr("Search transactions")}
            className="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
          />
        </div>
      </div>

      {!user && (
        <Card hover={false} className="text-sm text-text-secondary">
          {tr("Please log in to view and add transactions.")}
        </Card>
      )}

      {loading && (
        <Card hover={false} className="text-sm text-text-secondary">
          {tr("Loading transactions...")}
        </Card>
      )}

      {!loading && user && Object.keys(grouped).length === 0 && (
        <Card hover={false} className="text-sm text-text-secondary">
          {tr("No transactions yet. Add your first transaction using the plus button.")}
        </Card>
      )}

      {Object.entries(grouped).map(([date, items]) => (
        <div key={date}>
          <div className="mb-1.5 text-xs font-semibold text-text-muted">{date}</div>
          <Card className="divide-y divide-border/50 p-0" hover={false}>
            {items.map((t) => (
              <div key={t.id} className="flex items-center gap-3 px-3 py-2.5">
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-full text-sm"
                  style={{ background: (CAT_COLOR[t.category] ?? "#6b7280") + "26" }}
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: CAT_COLOR[t.category] ?? "#6b7280" }}
                  />
                </div>
                <div className="flex-1">
                  <div className="text-sm text-text-primary">{t.merchant}</div>
                  <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
                    <span className="rounded-[4px] bg-elevated px-1.5 py-0.5">{tr(t.category)}</span>
                    {t.source ?? "manual"}
                  </div>
                </div>
                <span
                  className={cn(
                    "font-mono text-sm font-medium tabular-nums",
                    Number(t.amount) >= 0 ? "text-bull" : "text-bear",
                  )}
                >
                  {Number(t.amount) >= 0 ? "+" : "-"}
                  {fmtPKR(Math.abs(Number(t.amount)))}
                </span>
                <button
                  type="button"
                  onClick={() => handleDelete(t.id)}
                  className="rounded-[6px] border border-bear/40 px-2 py-1 text-xs text-bear hover:bg-bear/10"
                >
                  {tr("Delete")}
                </button>
              </div>
            ))}
          </Card>
        </div>
      ))}

      <button
        onClick={() => setOpen(true)}
        className="safe-bottom fixed right-4 bottom-20 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-bull text-bull-foreground shadow-[0_4px_24px_rgba(0,0,0,0.5)] hover:brightness-110 lg:bottom-8"
      >
        <Plus className="h-6 w-6" />
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={tr("Add Transaction")}>
        <div className="space-y-3">
          <div className="flex gap-2">
            {(["expense", "income"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                className={cn(
                  "flex-1 rounded-[6px] border py-2 text-sm font-medium capitalize transition",
                  kind === k
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border text-text-secondary",
                )}
              >
                {tr(k === "expense" ? "Expense" : "Income")}
              </button>
            ))}
          </div>
          <input
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            placeholder={tr("Merchant / description")}
            className={fieldClass}
          />
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            placeholder={tr("Amount (PKR)")}
            className={fieldClass}
          />
          {kind === "expense" && (
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={fieldClass}
            >
              {CATEGORIES.filter((c) => c !== "Income").map((c) => (
                <option key={c} value={c}>
                  {tr(c)}
                </option>
              ))}
            </select>
          )}
          <select
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            className={fieldClass}
          >
            {ACCOUNTS.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            type="button"
            onClick={submit}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {tr("Add Transaction")}
          </button>
        </div>
      </Modal>
    </div>
  );
}


function Budgets() {
  const { t } = useLang();
  const { user } = useAuth();
  const { data: apiBudgets } = useFinanceBudgets(!!user);
  const [offset, setOffset] = useState(0);
  const base = new Date();
  const current = new Date(base.getFullYear(), base.getMonth() + offset, 1);
  const prev = new Date(current.getFullYear(), current.getMonth() - 1, 1);
  const next = new Date(current.getFullYear(), current.getMonth() + 1, 1);
  const shortMonth = (d: Date) => d.toLocaleString("en-US", { month: "short" });
  const longLabel = current.toLocaleString("en-US", { month: "long", year: "numeric" });

  const displayBudgets = user && apiBudgets && apiBudgets.length > 0
    ? apiBudgets.map((b) => ({ category: b.category, spent: b.spent, limit: b.limit_amount, tip: b.tip }))
    : BUDGETS;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center gap-4 text-sm text-text-secondary">
        <button onClick={() => setOffset((o) => o - 1)} className="hover:text-text-primary">
          ‹ {shortMonth(prev)}
        </button>
        <span className="font-semibold text-text-primary">{longLabel}</span>
        <button onClick={() => setOffset((o) => o + 1)} className="hover:text-text-primary">
          {shortMonth(next)} ›
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {displayBudgets.map((b) => {
          const pct = Math.round((b.spent / b.limit) * 100);
          const over = b.spent > b.limit;
          const color = over
            ? "bg-bear"
            : pct >= 90
              ? "bg-warning"
              : pct >= 80
                ? "bg-warning"
                : "bg-bull";
          return (
            <Card key={b.category}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text-primary">{t(b.category)}</span>
                <span
                  className={cn(
                    "font-mono text-xs tabular-nums",
                    over ? "text-bear" : "text-text-secondary",
                  )}
                >
                  {fmtPKR(b.spent)} / {fmtPKR(b.limit)}
                </span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
                <AnimatedBar value={Math.min(pct, 100)} className={color} />
              </div>
              {b.tip && (
                <div className="mt-2 flex items-start gap-1.5 rounded-[6px] border-l-2 border-ai bg-ai-tint px-2.5 py-1.5 text-[11px] text-text-secondary">
                  <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-ai" strokeWidth={1.5} />
                  {t(b.tip)}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function Bills() {
  const { t } = useLang();
  const { user } = useAuth();

  const [bills, setBills] = useState<FinanceBill[]>([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [busyBillId, setBusyBillId] = useState<string | null>(null);

  async function loadBills() {
    if (!user) {
      setBills([]);
      return;
    }

    try {
      setLoading(true);
      const data = await getFinanceBills(user.id);
      setBills(data ?? []);
    } catch (error) {
      console.error("Load bills error:", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBills();
  }, [user]);

  const getDisplayDue = (bill: FinanceBill) => {
    if (bill.due_label) return bill.due_label;
    if (!bill.due_date) return "—";

    return new Date(`${bill.due_date}T00:00:00`).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  const submit = async () => {
    setErr("");

    if (!user) return setErr(t("Please log in first."));

    const num = Number(amount);

    if (!name.trim()) return setErr(t("Please enter a bill name."));
    if (!amount || Number.isNaN(num) || num <= 0) return setErr(t("Please enter a valid amount."));

    try {
      const dueDate = due.trim() || null;

      await addFinanceBill(user.id, {
        name: name.trim(),
        amount: num,
        currency: "PKR",
        due_date: dueDate,
        due_label: dueDate
          ? new Date(`${dueDate}T00:00:00`).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })
          : null,
        status: "UPCOMING",
      });

      await loadBills();

      setName("");
      setAmount("");
      setDue("");
      setOpen(false);
    } catch (error) {
      console.error("Add bill error:", error);
      setErr(t("Failed to add bill."));
    }
  };

  const handleMarkPaid = async (bill: FinanceBill) => {
    if (!user) return;

    try {
      setBusyBillId(bill.id);
      await markFinanceBillPaid(bill.id, user.id);
      await loadBills();
    } catch (error) {
      console.error("Mark bill paid error:", error);
      alert("Failed to mark bill as paid.");
    } finally {
      setBusyBillId(null);
    }
  };

  const handleDelete = async (bill: FinanceBill) => {
    if (!user) return;

    const ok = confirm(`Delete ${bill.name}?`);
    if (!ok) return;

    try {
      setBusyBillId(bill.id);
      await deleteFinanceBill(bill.id, user.id);
      await loadBills();
    } catch (error) {
      console.error("Delete bill error:", error);
      alert("Failed to delete bill.");
    } finally {
      setBusyBillId(null);
    }
  };

  return (
    <div className="space-y-3">
      {!user && (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("Please log in to view and add bills.")}
        </Card>
      )}

      {loading && (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("Loading bills...")}
        </Card>
      )}

      {!loading && user && bills.length === 0 && (
        <Card hover={false} className="text-sm text-text-secondary">
          {t("No bills yet. Add your first bill below.")}
        </Card>
      )}

      {bills.map((b) => (
        <Card key={b.id} className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-elevated text-sm font-bold text-text-secondary">
            {b.name[0]}
          </div>
          <div className="flex-1">
            <div className="text-sm font-medium text-text-primary">{t(b.name)}</div>
            <div className="text-[11px] text-text-muted">
              {t("Due")} {getDisplayDue(b)}
            </div>
          </div>
          <span className="font-mono text-sm font-medium tabular-nums text-text-primary">
            {fmtPKR(Number(b.amount))}
          </span>
          <span
            className={cn(
              "rounded-[4px] px-2 py-0.5 text-[10px] font-semibold",
              b.status === "DUE SOON"
                ? "bg-warning/20 text-warning"
                : b.status === "PAID"
                  ? "bg-bull/20 text-bull"
                  : "bg-elevated text-text-secondary",
            )}
          >
            {t(b.status)}
          </span>
          <button
            type="button"
            disabled={busyBillId === b.id || b.status === "PAID"}
            onClick={() => handleMarkPaid(b)}
            title={t("Mark as paid")}
            className="flex h-8 w-8 items-center justify-center rounded-full border border-bull text-bull hover:bg-bull/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={busyBillId === b.id}
            onClick={() => handleDelete(b)}
            className="rounded-[6px] border border-bear/40 px-2 py-1 text-xs text-bear hover:bg-bear/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("Delete")}
          </button>
        </Card>
      ))}

      <button
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-[6px] border border-dashed border-border py-3 text-sm font-medium text-text-secondary hover:border-bull hover:text-bull"
      >
        <Plus className="h-4 w-4" />
        {t("Add Bill")}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={t("Add Bill")}>
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("Bill name")}
            className={fieldClass}
          />
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="decimal"
            placeholder={t("Amount (PKR)")}
            className={fieldClass}
          />
          <input
            value={due}
            onChange={(e) => setDue(e.target.value)}
            type="date"
            className={fieldClass}
          />
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            type="button"
            onClick={submit}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Add Bill")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

function Goals() {
  const { t } = useLang();
  const { user } = useAuth();
  const { goals: storeGoals } = useFinanceStore();
  const { data: apiGoals } = useApiFinanceGoals(!!user);
  const createGoalApi = useApiCreateGoal();
  const contributeGoalApi = useApiContributeGoal();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [date, setDate] = useState<Date | undefined>(undefined);
  const [dateOpen, setDateOpen] = useState(false);
  const [err, setErr] = useState("");
  const [contribGoal, setContribGoal] = useState<string | null>(null);
  const [contribAmount, setContribAmount] = useState("");
  const [contribErr, setContribErr] = useState("");

  const displayGoals: Goal[] = user && apiGoals && apiGoals.length > 0
    ? apiGoals.map((g) => ({
        emoji: g.emoji || "🎯",
        name: g.name,
        target: g.target,
        saved: g.saved,
        color: (g.color === "warning" ? "warning" : "bull") as "warning" | "bull",
        ai: g.ai_tip || "",
        date: g.target_date || undefined,
      }))
    : storeGoals;

  const submit = () => {
    setErr("");
    const num = Number(target);
    if (!name.trim()) return setErr(t("Please enter a goal name."));
    if (!target || Number.isNaN(num) || num <= 0)
      return setErr(t("Please enter a valid target amount."));
    if (user) {
      createGoalApi.mutate({
        name: name.trim(),
        target: num,
        emoji: "🎯",
        color: "bull",
        target_date: date ? date.toISOString() : undefined,
      });
    } else {
      const goal: Goal = {
        emoji: "🎯",
        name: name.trim(),
        target: num,
        saved: 0,
        color: "bull",
        date: date ? format(date, "MMM d, yyyy") : undefined,
        ai: t("New goal created. Start contributing to track your progress."),
      };
      financeActions.addGoal(goal);
    }
    setName("");
    setTarget("");
    setDate(undefined);
    setOpen(false);
  };

  const openContribute = (goalName: string) => {
    setContribGoal(goalName);
    setContribAmount("");
    setContribErr("");
  };

  const submitContribute = () => {
    setContribErr("");
    const num = Number(contribAmount);
    if (!contribAmount || Number.isNaN(num) || num <= 0)
      return setContribErr(t("Please enter a valid amount."));
    if (contribGoal) {
      if (user && apiGoals) {
        const goal = apiGoals.find((g) => g.name === contribGoal);
        if (goal) contributeGoalApi.mutate({ id: goal.id, amount: num });
      } else {
        financeActions.contributeToGoal(contribGoal, num);
      }
    }
    setContribGoal(null);
    setContribAmount("");
  };


  return (
    <div className="grid gap-4 md:grid-cols-2">
      {displayGoals.map((g) => {
        const pct = Math.round((g.saved / g.target) * 100);
        return (
          <Card key={g.name}>
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
              {t("Target")} {fmtPKR(g.target)} · {t("Saved")} {fmtPKR(g.saved)}
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-elevated">
              <AnimatedBar value={pct} className={g.color === "bull" ? "bg-bull" : "bg-warning"} />
            </div>
            {g.date && (
              <div className="mt-2 text-[11px] text-text-muted">{t("Target date:")} {g.date}</div>
            )}
            <div className="mt-2 rounded-[6px] border-l-2 border-ai bg-ai-tint px-2.5 py-1.5 text-[11px] text-text-secondary">
              <Sparkles className="mr-1 inline h-3 w-3 text-ai" />
              {t(g.ai)}
            </div>
            <button
              onClick={() => openContribute(g.name)}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-[6px] border border-bull/40 py-1.5 text-xs font-semibold text-bull hover:bg-bull/10"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("Add Contribution")}
            </button>
          </Card>
        );
      })}
      <button
        onClick={() => setOpen(true)}
        className="flex min-h-[120px] items-center justify-center gap-1.5 rounded-[8px] border border-dashed border-border text-sm font-medium text-text-secondary hover:border-bull hover:text-bull"
      >
        <Plus className="h-4 w-4" />
        {t("Add Goal")}
      </button>

      <Modal open={open} onClose={() => setOpen(false)} title={t("Add Goal")}>
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("Goal name")}
            className={fieldClass}
          />
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            inputMode="decimal"
            placeholder={t("Target amount (PKR)")}
            className={fieldClass}
          />
          <Popover open={dateOpen} onOpenChange={setDateOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className={cn(
                  fieldClass,
                  "flex items-center gap-2 text-left",
                  !date && "text-text-muted",
                )}
              >
                <CalendarIcon className="h-4 w-4 shrink-0" />
                {date ? format(date, "MMM d, yyyy") : t("Target date (optional)")}
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={date}
                onSelect={(d) => {
                  setDate(d);
                  setDateOpen(false);
                }}
                initialFocus
                className="pointer-events-auto p-3"
              />
            </PopoverContent>
          </Popover>
          {err && <div className="text-xs text-bear">{err}</div>}
          <button
            onClick={submit}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Add Goal")}
          </button>
        </div>
      </Modal>

      <Modal
        open={contribGoal != null}
        onClose={() => setContribGoal(null)}
        title={`${t("Add Contribution")}${contribGoal ? ` — ${t(contribGoal)}` : ""}`}
      >
        <div className="space-y-3">
          <input
            value={contribAmount}
            onChange={(e) => setContribAmount(e.target.value)}
            inputMode="decimal"
            autoFocus
            placeholder={t("Amount (PKR)")}
            className={fieldClass}
            onKeyDown={(e) => e.key === "Enter" && submitContribute()}
          />
          {contribErr && <div className="text-xs text-bear">{contribErr}</div>}
          <button
            onClick={submitContribute}
            className="w-full rounded-[6px] bg-bull py-2 text-sm font-semibold text-bull-foreground hover:brightness-110"
          >
            {t("Add Contribution")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

function FinanceReportModal({ onClose }: { onClose: () => void }) {
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
            {t("AI Finance Report")}
          </h3>
          <button onClick={onClose}>
            <X className="h-5 w-5 text-text-secondary" />
          </button>
        </div>
        <div className="rounded-[10px] border border-white/[0.08] bg-surface-alt p-4 text-center">
          <p className="text-sm font-semibold text-text-primary">Coming soon</p>
          <p className="mt-2 text-xs leading-relaxed text-text-secondary">
            Real AI insights from your income, expenses, and budgets are coming soon. For now, review your live KPIs on the Overview tab.
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

/* ---------------- Zakat Calculator ---------------- */

const NISAB = 135000; // PKR — silver-based nisab threshold
const ZAKAT_RATE = 0.025;

interface ZakatLine {
  key: string;
  label: string;
  sub: string;
}

const ASSET_LINES: ZakatLine[] = [
  { key: "cash", label: "Cash & Bank Balance", sub: "Linked bank accounts" },
  { key: "gold", label: "Gold & Jewelry", sub: "Self-reported" },
  { key: "stocks", label: "Stocks (PSX)", sub: "Portfolio" },
  { key: "funds", label: "Mutual Funds", sub: "Portfolio" },
  { key: "business", label: "Business Inventory", sub: "Self-reported" },
  { key: "property", label: "Property (non-primary)", sub: "Self-reported" },
];

const LIABILITY_LINES: ZakatLine[] = [
  { key: "loans", label: "Outstanding Loans", sub: "Self-reported" },
  { key: "credit", label: "Credit Card Debt", sub: "Self-reported" },
];

const ZAKAT_DEFAULTS: Record<string, number> = {
  cash: 850000,
  gold: 420000,
  stocks: 4250000,
  funds: 500000,
  business: 0,
  property: 0,
  loans: 200000,
  credit: 45000,
};

function ZakatNumberInput({
  value,
  onChange,
  ariaLabel,
}: {
  value: number;
  onChange: (n: number) => void;
  ariaLabel: string;
}) {
  return (
    <input
      inputMode="numeric"
      aria-label={ariaLabel}
      value={value === 0 ? "" : String(value)}
      placeholder="0"
      onChange={(e) => {
        const cleaned = e.target.value.replace(/[^0-9]/g, "");
        onChange(cleaned === "" ? 0 : Number(cleaned));
      }}
      className="w-[150px] rounded-[8px] border border-white/[0.08] bg-elevated/60 px-3 py-2 text-right font-mono text-sm font-semibold tabular-nums text-text-primary outline-none transition-colors focus:border-primary/50 focus:bg-elevated"
    />
  );
}

function Zakat() {
  const { t } = useLang();
  const [values, setValues] = useState<Record<string, number>>({ ...ZAKAT_DEFAULTS });

  const set = (key: string, n: number) => setValues((v) => ({ ...v, [key]: n }));

  const totalAssets = ASSET_LINES.reduce((s, l) => s + (values[l.key] || 0), 0);
  const totalLiabilities = LIABILITY_LINES.reduce((s, l) => s + (values[l.key] || 0), 0);
  const zakatableWealth = Math.max(totalAssets - totalLiabilities, 0);
  const aboveNisab = zakatableWealth >= NISAB;
  const zakatDue = aboveNisab ? Math.round(zakatableWealth * ZAKAT_RATE) : 0;

  const exportPdf = () => {
    if (typeof window === "undefined") return;
    const rows = (lines: ZakatLine[]) =>
      lines
        .map(
          (l) =>
            `<tr><td>${t(l.label)}</td><td style="text-align:right">PKR ${formatNumber(values[l.key] || 0, 0)}</td></tr>`,
        )
        .join("");
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>Zakat Statement — NafaIQ</title>
      <style>
        body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;padding:40px;max-width:640px;margin:auto}
        h1{font-size:22px;margin:0 0 4px}p.sub{color:#64748b;margin:0 0 24px;font-size:13px}
        h2{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:#334155;margin:24px 0 8px;border-bottom:1px solid #e2e8f0;padding-bottom:6px}
        table{width:100%;border-collapse:collapse;font-size:14px}td{padding:6px 0}
        .total{font-weight:700;border-top:1px solid #cbd5e1}
        .final{margin-top:28px;padding:20px;border-radius:12px;background:#ecfdf5;text-align:center}
        .final .amt{font-size:30px;font-weight:800;color:#047857}
      </style></head><body>
      <h1>Zakat Statement</h1><p class="sub">Generated by NafaIQ · ${new Date().toLocaleDateString()}</p>
      <h2>${t("Zakatable Assets")}</h2><table>${rows(ASSET_LINES)}<tr class="total"><td>${t("Total Assets")}</td><td style="text-align:right">PKR ${formatNumber(totalAssets, 0)}</td></tr></table>
      <h2>${t("Liabilities")}</h2><table>${rows(LIABILITY_LINES)}<tr class="total"><td>Total Liabilities</td><td style="text-align:right">PKR ${formatNumber(totalLiabilities, 0)}</td></tr></table>
      <h2>Summary</h2><table>
        <tr><td>${t("Nisab Threshold")}</td><td style="text-align:right">PKR ${formatNumber(NISAB, 0)}</td></tr>
        <tr><td>${t("Zakatable Wealth")}</td><td style="text-align:right">PKR ${formatNumber(zakatableWealth, 0)}</td></tr>
      </table>
      <div class="final"><div>${t("Zakat Due (2.5%)")}</div><div class="amt">PKR ${formatNumber(zakatDue, 0)}</div></div>
      </body></html>`;
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(html);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 300);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      {/* Zakatable Assets */}
      <Card hover={false}>
        <div className="mb-5 flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-primary/20 bg-primary/[0.08] text-primary">
            <Coins className="h-4 w-4" />
          </span>
          <h3 className="text-base font-semibold text-text-primary">{t("Zakatable Assets")}</h3>
        </div>
        <div className="space-y-4">
          {ASSET_LINES.map((l) => (
            <div key={l.key} className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-text-primary">{t(l.label)}</div>
                <div className="text-xs text-text-muted">{t(l.sub)}</div>
              </div>
              <ZakatNumberInput
                value={values[l.key] || 0}
                onChange={(n) => set(l.key, n)}
                ariaLabel={t(l.label)}
              />
            </div>
          ))}
        </div>
        <div className="mt-5 flex items-center justify-between border-t border-white/[0.06] pt-4">
          <span className="text-sm font-bold text-text-primary">{t("Total Assets")}</span>
          <span className="font-mono text-base font-bold tabular-nums text-text-primary">
            <CountUpNumber value={totalAssets} prefix="PKR " preserveValue />
          </span>
        </div>
      </Card>

      {/* Right column */}
      <div className="space-y-6">
        {/* Liabilities */}
        <Card hover={false}>
          <h3 className="mb-4 text-base font-semibold text-text-primary">{t("Liabilities")}</h3>
          <div className="space-y-4">
            {LIABILITY_LINES.map((l) => (
              <div key={l.key} className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-text-primary">
                    {t(l.label)}
                  </div>
                  <div className="text-xs text-text-muted">{t(l.sub)}</div>
                </div>
                <ZakatNumberInput
                  value={values[l.key] || 0}
                  onChange={(n) => set(l.key, n)}
                  ariaLabel={t(l.label)}
                />
              </div>
            ))}
          </div>
        </Card>

        {/* Nisab */}
        <Card hover={false} className="text-center">
          <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-text-secondary">
            <Scale className="h-3.5 w-3.5" />
            {t("Nisab Threshold")}
          </div>
          <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-gold">
            <CountUpNumber value={NISAB} prefix="PKR " preserveValue />
          </div>
          <div
            className={cn(
              "mt-2 text-sm font-semibold",
              aboveNisab ? "text-bull" : "text-text-muted",
            )}
          >
            {aboveNisab ? t("✓ Above Nisab — Zakat Due") : t("Below Nisab — No Zakat Due")}
          </div>
        </Card>

        {/* Result */}
        <Card hover={false} className="text-center">
          <div className="text-xs font-medium text-text-secondary">{t("Zakatable Wealth")}</div>
          <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-text-primary">
            <CountUpNumber value={zakatableWealth} prefix="PKR " preserveValue />
          </div>
          <div className="mt-4 text-xs font-medium text-text-secondary">
            {t("Zakat Due (2.5%)")}
          </div>
          <div className="mt-1 font-mono text-3xl font-extrabold tabular-nums text-bull">
            <CountUpNumber value={zakatDue} prefix="PKR " preserveValue />
          </div>
          <button
            onClick={exportPdf}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-[10px] bg-primary py-2.5 text-sm font-semibold text-primary-foreground transition-all duration-200 hover:brightness-110"
          >
            <FileDown className="h-4 w-4" />
            {t("Export as PDF")}
          </button>
          <p className="mt-3 text-[10px] italic leading-relaxed text-text-muted">
            {t(
              "Estimates for guidance only. Nisab and rulings vary by scholar — consult a qualified authority.",
            )}
          </p>
        </Card>
      </div>
    </div>
  );
}
