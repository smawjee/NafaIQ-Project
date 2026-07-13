// Personal Finance (`/finance`). Mirrors web `/finance`: tabbed Overview /
// Transactions / Budgets / Bills / Goals. Backed by the FastAPI finance
// endpoints via React Query hooks (src/hooks/queries/use-finance*.ts); list
// tabs are virtualized FlatLists.
import { memo, useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Sparkline } from "@/components/charts/Sparkline";
import { IncomeExpenseChart } from "@/components/charts/IncomeExpenseChart";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { GlassSheet } from "@/components/glass/GlassSheet";
import { Field } from "@/components/Modal";
import { Button, Text } from "@/components/ui";
import { ChipRow, Segmented } from "@/components/ui/controls";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import {
  type FinanceBill,
  type FinanceBudget,
  type FinanceGoal,
  type FinanceTransaction,
  useContributeGoal,
  useCreateBill,
  useCreateBudget,
  useCreateGoal,
  useCreateTransaction,
  useFinanceBills,
  useFinanceBudgets,
  useFinanceGoals,
  useFinanceSummary,
  useFinanceTransactions,
  useMarkBillPaid,
} from "@/hooks/queries/use-finance";
import { useIncomeExpenseSeries } from "@/hooks/queries/use-finance-series";
import { fmtPKR } from "@nafaiq/shared";
import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  Lightbulb,
  Percent,
  PiggyBank,
  Plus,
  Search,
  Sparkles,
  Target,
} from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });
const TABS = ["Overview", "Transactions", "Budgets", "Bills", "Goals"];
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
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const CATEGORIES = ["Food & Dining", "Utilities", "Transport", "Groceries", "Shopping", "Subscriptions", "Savings"];
const ACCOUNTS = ["HBL Current", "Meezan Debit", "Easypaisa", "Meezan Savings"];

/** "+PKR 2,500" / "-PKR 1,200" — matches web formatSignedPKR intent. */
function signedPKR(n: number) {
  return `${n >= 0 ? "+" : "-"}${fmtPKR(Math.abs(n))}`;
}

/** Empty 6-month series so the chart keeps its shape before data arrives. */
function emptyIncomeExpenseSeries(n: number) {
  const now = new Date();
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (n - 1 - i), 1);
    return { month: MONTHS[d.getMonth()], income: 0, expense: 0 };
  });
}

export default function FinanceScreen() {
  const [tab, setTab] = useState("Overview");
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <GlassScreen>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.header}>
          <Text variant="display" style={{ fontFamily: AVENIR }}>Personal Finance</Text>
          <Segmented options={TABS} value={tab} onChange={setTab} />
        </View>
        {tab === "Overview" && <Overview />}
        {tab === "Transactions" && <Transactions />}
        {tab === "Budgets" && <Budgets />}
        {tab === "Bills" && <Bills />}
        {tab === "Goals" && <Goals />}
      </SafeAreaView>
    </GlassScreen>
  );
}

/* --------------------------- shared state cards --------------------------- */
function LoadingCard({ label }: { label: string }) {
  const { colors } = useTheme();
  return (
    <GlassCard style={{ padding: 22, alignItems: "center", gap: 10 }}>
      <ActivityIndicator color={colors.primary} accessibilityLabel={label} />
      <Text variant="muted">{label}</Text>
    </GlassCard>
  );
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { colors } = useTheme();
  return (
    <GlassCard style={{ padding: 22, alignItems: "center", gap: 10 }}>
      <Text variant="secondary" style={{ textAlign: "center" }}>{message}</Text>
      <Button title="Retry" variant="outline" onPress={onRetry} />
      <Text variant="muted" style={{ fontSize: 11, color: colors.textMuted, textAlign: "center" }}>
        Check your connection and try again.
      </Text>
    </GlassCard>
  );
}

function EmptyCard({ title, sub }: { title: string; sub?: string }) {
  return (
    <GlassCard style={{ padding: 22, alignItems: "center", gap: 4 }}>
      <Text variant="secondary" style={{ textAlign: "center" }}>{title}</Text>
      {sub ? <Text variant="muted" style={{ textAlign: "center" }}>{sub}</Text> : null}
    </GlassCard>
  );
}

/* ------------------------------- Overview -------------------------------- */
function Kpi({
  icon,
  label,
  value,
  color,
  sub,
  subColor,
  spark,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
  sub?: string;
  subColor?: string;
  spark?: number[];
}) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <GlassCard style={styles.kpi}>
      <View style={[styles.iconChip, { backgroundColor: color + "22" }]}>{icon}</View>
      <Text variant="muted" style={{ textTransform: "uppercase", letterSpacing: 1, fontSize: 10, marginTop: 8 }}>
        {label}
      </Text>
      <Text style={{ color, fontFamily: fonts.mono, fontSize: 18, fontWeight: "700", marginTop: 2 }}>
        {value}
      </Text>
      <View style={{ flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", marginTop: 6 }}>
        {sub ? (
          <Text variant="muted" style={[{ flex: 1 }, subColor ? { color: subColor } : null]}>{sub}</Text>
        ) : (
          <View style={{ flex: 1 }} />
        )}
        {spark && spark.length >= 2 ? <Sparkline data={spark} width={48} height={20} color={color} /> : null}
      </View>
    </GlassCard>
  );
}

function Overview() {
  const { width } = useWindowDimensions();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const summaryQ = useFinanceSummary();
  const seriesQ = useIncomeExpenseSeries(6);

  if (summaryQ.isPending || seriesQ.isPending) {
    return (
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <LoadingCard label="Loading finance overview…" />
      </ScrollView>
    );
  }
  if (summaryQ.isError || seriesQ.isError) {
    return (
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <ErrorCard
          message="Could not load your finance overview."
          onRetry={() => {
            summaryQ.refetch();
            seriesQ.refetch();
          }}
        />
      </ScrollView>
    );
  }

  const s = summaryQ.data;
  const income = s?.income ?? 0;
  const expenses = s?.expenses ?? 0;
  const savings = s?.savings ?? 0;
  const rate = s?.savings_rate ?? 0;
  const lastIncome = s?.last_month_income ?? 0;
  const lastExpense = s?.last_month_expense ?? 0;
  const lastSavings = s?.last_month_savings ?? 0;
  const incomeDelta = income - lastIncome;
  const expenseDeltaPct = lastExpense > 0 ? ((expenses - lastExpense) / lastExpense) * 100 : 0;
  const savingsDelta = savings - lastSavings;

  const series = seriesQ.data?.series ?? [];
  const hasSeries = series.length > 0;
  const chartData = hasSeries ? series : emptyIncomeExpenseSeries(6);
  const incomeSpark = hasSeries ? series.slice(-3).map((p) => p.income) : undefined;
  const expenseSpark = hasSeries ? series.slice(-3).map((p) => p.expense) : undefined;
  const totalSaved = Math.round(series.reduce((a, p) => a + p.income - p.expense, 0));

  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.grid}>
        <Kpi
          icon={<ArrowUpRight color={colors.bull} size={18} />}
          label="Monthly Income"
          value={fmtPKR(income)}
          color={colors.bull}
          sub={`${signedPKR(incomeDelta)} vs last`}
          subColor={incomeDelta >= 0 ? colors.bull : colors.bear}
          spark={incomeSpark}
        />
        <Kpi
          icon={<ArrowDownRight color={colors.bear} size={18} />}
          label="Total Expenses"
          value={fmtPKR(expenses)}
          color={colors.bear}
          sub={`${expenseDeltaPct >= 0 ? "+" : ""}${expenseDeltaPct.toFixed(1)}% vs last`}
          subColor={expenseDeltaPct <= 0 ? colors.bull : colors.bear}
          spark={expenseSpark}
        />
        <Kpi
          icon={<PiggyBank color={colors.ai} size={18} />}
          label="Net Savings"
          value={fmtPKR(savings)}
          color={colors.ai}
          sub={signedPKR(savingsDelta)}
          subColor={savingsDelta >= 0 ? colors.bull : colors.bear}
        />
        <Kpi
          icon={<Percent color={colors.warning} size={18} />}
          label="Savings Rate"
          value={`${rate.toFixed(1)}%`}
          color={colors.warning}
          sub="Goal: 65%"
        />
      </View>

      <GlassCard style={{ gap: 12, padding: 16 }}>
        <View style={styles.between}>
          <Text variant="title">6-Month Overview</Text>
          <View style={{ flexDirection: "row", gap: 12 }}>
            <Legend color={colors.bull} label="In" />
            <Legend color={colors.bear} label="Out" />
          </View>
        </View>
        <IncomeExpenseChart data={chartData} width={width - 64} />
        <Text variant="muted" style={{ textAlign: "center" }}>
          {hasSeries
            ? `Saved ${fmtPKR(totalSaved)} over ${series.length} months`
            : "No activity yet — add transactions to see your trend."}
        </Text>
      </GlassCard>
    </ScrollView>
  );
}

/* ----------------------------- Transactions ------------------------------ */
interface TxnGroup {
  date: string;
  items: FinanceTransaction[];
}

const TxnGroupCard = memo(function TxnGroupCard({ group }: { group: TxnGroup }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={{ gap: 6 }}>
      <Text variant="muted" style={{ fontWeight: "600" }}>{group.date}</Text>
      <GlassCard style={{ gap: 0, padding: 0 }}>
        {group.items.map((tx, i) => {
          const isIncome = tx.transaction_type === "income";
          return (
            <View key={tx.id} style={[styles.txn, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
              <View style={[styles.dot, { backgroundColor: (CAT_COLOR[tx.category] ?? "#6b7280") + "33" }]}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: CAT_COLOR[tx.category] ?? "#6b7280" }} />
              </View>
              <View style={{ flex: 1 }}>
                <Text variant="body">{tx.merchant}</Text>
                <Text variant="muted">{tx.category} · {tx.source ?? "manual"}</Text>
              </View>
              <Text style={{ color: isIncome ? colors.bull : colors.bear, fontFamily: fonts.mono, fontSize: 13 }}>
                {isIncome ? "+" : "-"}
                {fmtPKR(Math.abs(Number(tx.amount) || 0))}
              </Text>
            </View>
          );
        })}
      </GlassCard>
    </View>
  );
});

function Transactions() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { data: transactions = [], isPending, isError, refetch } = useFinanceTransactions();
  const createTransaction = useCreateTransaction();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [account, setAccount] = useState(ACCOUNTS[0]);
  const [err, setErr] = useState("");

  const groups = useMemo<TxnGroup[]>(() => {
    const ql = q.trim().toLowerCase();
    const filtered = transactions.filter(
      (tx) =>
        !ql ||
        tx.merchant?.toLowerCase().includes(ql) ||
        tx.category?.toLowerCase().includes(ql) ||
        tx.transaction_type?.toLowerCase().includes(ql) ||
        (tx.source ?? "").toLowerCase().includes(ql),
    );
    const map = new Map<string, FinanceTransaction[]>();
    for (const tx of filtered) {
      const parsed = tx.transaction_date ? new Date(tx.transaction_date) : null;
      const label =
        parsed && !Number.isNaN(parsed.getTime())
          ? parsed.toLocaleDateString("en-US", { month: "long", day: "numeric" })
          : "No Date";
      const arr = map.get(label);
      if (arr) arr.push(tx);
      else map.set(label, [tx]);
    }
    return [...map.entries()].map(([date, items]) => ({ date, items }));
  }, [q, transactions]);

  function submit() {
    setErr("");
    const num = Number(amount);
    if (!merchant.trim()) return setErr("Please enter a merchant name.");
    if (!amount || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid amount.");
    createTransaction.mutate(
      {
        merchant: merchant.trim(),
        amount: num,
        transaction_type: kind,
        category: kind === "income" ? "Income" : category,
        transaction_date: new Date().toISOString(),
        source: account,
        note: null,
      },
      {
        onSuccess: () => {
          setMerchant("");
          setAmount("");
          setKind("expense");
          setOpen(false);
        },
        onError: () => setErr("Failed to add transaction. Please try again."),
      },
    );
  }

  const renderGroup = useCallback(({ item }: { item: TxnGroup }) => <TxnGroupCard group={item} />, []);

  return (
    <>
      <FlatList
        data={groups}
        keyExtractor={(g) => g.date}
        renderItem={renderGroup}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={
          <View style={styles.search}>
            <Search color={colors.textMuted} size={16} />
            <TextInput
              value={q}
              onChangeText={setQ}
              placeholder="Search transactions"
              placeholderTextColor={colors.textMuted}
              style={{ flex: 1, color: colors.textPrimary }}
              accessibilityLabel="Search transactions"
            />
          </View>
        }
        ListEmptyComponent={
          isPending ? (
            <LoadingCard label="Loading transactions…" />
          ) : isError ? (
            <ErrorCard message="Could not load transactions." onRetry={refetch} />
          ) : (
            <EmptyCard
              title={q ? "No transactions match your search." : "No transactions yet."}
              sub={q ? undefined : "Add your first transaction below."}
            />
          )
        }
        ListFooterComponent={
          <Pressable
            style={styles.dashed}
            onPress={() => setOpen(true)}
            accessibilityRole="button"
            accessibilityLabel="Add transaction"
          >
            <Plus color={colors.textSecondary} size={16} />
            <Text variant="secondary">Add Transaction</Text>
          </Pressable>
        }
      />

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Transaction">
        <ChipRow options={["expense", "income"]} value={kind} onChange={(v) => setKind(v as "expense" | "income")} />
        <Field label="Merchant" value={merchant} onChangeText={setMerchant} placeholder="e.g. Imtiaz Super Market" />
        <Field label="Amount (PKR)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="0" />
        {kind === "expense" ? <ChipRow options={CATEGORIES} value={category} onChange={setCategory} /> : null}
        <ChipRow options={ACCOUNTS} value={account} onChange={setAccount} />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Transaction" onPress={submit} loading={createTransaction.isPending} />
      </GlassSheet>
    </>
  );
}

/* ------------------------------- Budgets --------------------------------- */
const BudgetCard = memo(function BudgetCard({ budget }: { budget: FinanceBudget }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const limit = Number(budget.limit_amount) || 0;
  const spent = Number(budget.spent) || 0;
  const pct = limit > 0 ? spent / limit : 0;
  const over = spent > limit;
  const c = over ? colors.bear : pct >= 0.8 ? colors.warning : colors.bull;
  return (
    <GlassCard style={{ gap: 8, padding: 14 }}>
      <View style={styles.between}>
        <Text style={{ fontWeight: "600" }}>{budget.category}</Text>
        <Text style={{ color: over ? colors.bear : colors.textSecondary, fontFamily: fonts.mono, fontSize: 12 }}>
          {fmtPKR(spent)} / {fmtPKR(limit)}
        </Text>
      </View>
      <ProgressBar value={Math.min(pct, 1)} color={c} />
      {budget.tip ? (
        <View style={styles.tip}>
          <Lightbulb color={colors.ai} size={13} />
          <Text variant="secondary" style={{ flex: 1, fontSize: 12 }}>{budget.tip}</Text>
        </View>
      ) : null}
    </GlassCard>
  );
});

function Budgets() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { data: budgets = [], isPending, isError, refetch } = useFinanceBudgets();
  const createBudget = useCreateBudget();
  // Month navigation matches the web Budgets component: the API returns one
  // monthly budget set, the nav is a display affordance.
  const [offset, setOffset] = useState(0);
  const now = new Date();
  const current = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const monthLabel = `${MONTHS[current.getMonth()]} ${current.getFullYear()}`;
  const prevLabel = MONTHS[new Date(current.getFullYear(), current.getMonth() - 1, 1).getMonth()];
  const nextLabel = MONTHS[new Date(current.getFullYear(), current.getMonth() + 1, 1).getMonth()];

  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [limit, setLimit] = useState("");
  const [tip, setTip] = useState("");
  const [err, setErr] = useState("");

  function submit() {
    setErr("");
    const num = Number(limit);
    if (!limit || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid monthly limit.");
    createBudget.mutate(
      { category, limit_amount: num, tip: tip.trim() || undefined },
      {
        onSuccess: () => {
          setCategory(CATEGORIES[0]);
          setLimit("");
          setTip("");
          setOpen(false);
        },
        onError: () =>
          setErr("Could not add budget — it may already exist or you've hit your plan limit."),
      },
    );
  }

  const renderBudget = useCallback(({ item }: { item: FinanceBudget }) => <BudgetCard budget={item} />, []);

  return (
    <>
      <FlatList
        data={budgets}
        keyExtractor={(b) => String(b.id)}
        renderItem={renderBudget}
        contentContainerStyle={[styles.content, { gap: 12 }]}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <View style={styles.monthNav}>
            <Pressable onPress={() => setOffset((o) => o - 1)} hitSlop={12} accessibilityRole="button" accessibilityLabel="Previous month">
              <Text style={{ color: colors.textSecondary }}>‹ {prevLabel}</Text>
            </Pressable>
            <Text style={{ fontWeight: "700" }}>{monthLabel}</Text>
            <Pressable onPress={() => setOffset((o) => o + 1)} hitSlop={12} accessibilityRole="button" accessibilityLabel="Next month">
              <Text style={{ color: colors.textSecondary }}>{nextLabel} ›</Text>
            </Pressable>
          </View>
        }
        ListEmptyComponent={
          isPending ? (
            <LoadingCard label="Loading budgets…" />
          ) : isError ? (
            <ErrorCard message="Could not load budgets." onRetry={refetch} />
          ) : (
            <EmptyCard
              title="No budgets yet."
              sub="Add your first budget to start tracking spending."
            />
          )
        }
        ListFooterComponent={
          <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel="Add budget">
            <Plus color={colors.textSecondary} size={16} />
            <Text variant="secondary">Add Budget</Text>
          </Pressable>
        }
      />

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Budget">
        <View style={{ gap: 4 }}>
          <Text variant="secondary">Category</Text>
          <ChipRow options={CATEGORIES} value={category} onChange={setCategory} />
        </View>
        <Field label="Monthly limit (PKR)" value={limit} onChangeText={setLimit} keyboardType="numeric" placeholder="0" />
        <Field label="Tip (optional)" value={tip} onChangeText={setTip} placeholder="e.g. Stay under limit to save for Hajj" />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Budget" onPress={submit} loading={createBudget.isPending} />
      </GlassSheet>
    </>
  );
}

/* -------------------------------- Bills ---------------------------------- */
function billDueLabel(bill: FinanceBill): string {
  if (!bill.due_date) return "—";
  const raw = bill.due_date.includes("T") ? bill.due_date : `${bill.due_date}T00:00:00`;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return bill.due_date;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const BillCard = memo(function BillCard({
  bill,
  busy,
  onMarkPaid,
}: {
  bill: FinanceBill;
  busy: boolean;
  onMarkPaid: (bill: FinanceBill) => void;
}) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const paid = bill.status === "PAID";
  const badgeBg =
    bill.status === "DUE SOON" ? colors.warning + "33" : paid ? colors.bull + "33" : colors.elevated;
  const badgeColor =
    bill.status === "DUE SOON" ? colors.warning : paid ? colors.bull : colors.textSecondary;
  return (
    <GlassCard style={styles.billRow}>
      <View style={styles.avatar}>
        <Text style={{ fontWeight: "700", color: colors.textSecondary }}>{bill.name?.[0] ?? "?"}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontWeight: "600" }} numberOfLines={1}>{bill.name}</Text>
        <Text variant="muted">Due {billDueLabel(bill)}</Text>
      </View>
      <View style={{ alignItems: "flex-end", gap: 5 }}>
        <Text variant="mono" style={{ fontSize: 13 }}>{fmtPKR(Number(bill.amount) || 0)}</Text>
        <View style={[styles.statusBadge, { backgroundColor: badgeBg }]}>
          <Text style={{ fontSize: 10, fontWeight: "700", color: badgeColor }}>{bill.status}</Text>
        </View>
      </View>
      <Pressable
        style={[styles.checkBtn, (paid || busy) && { opacity: 0.4 }]}
        onPress={() => onMarkPaid(bill)}
        disabled={paid || busy}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={paid ? `${bill.name} already paid` : `Mark ${bill.name} paid`}
        accessibilityState={{ disabled: paid || busy, busy }}
      >
        {busy ? <ActivityIndicator size="small" color={colors.bull} /> : <Check color={colors.bull} size={16} />}
      </Pressable>
    </GlassCard>
  );
});

function Bills() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { data: bills = [], isPending, isError, refetch } = useFinanceBills();
  const createBill = useCreateBill();
  const markBillPaid = useMarkBillPaid();
  const [busyBillId, setBusyBillId] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [due, setDue] = useState("");
  const [err, setErr] = useState("");

  function submit() {
    setErr("");
    const num = Number(amount);
    if (!name.trim()) return setErr("Please enter a bill name.");
    if (!amount || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid amount.");
    createBill.mutate(
      { name: name.trim(), amount: num, due_date: due.trim() || null, status: "UPCOMING" },
      {
        onSuccess: () => {
          setName("");
          setAmount("");
          setDue("");
          setOpen(false);
        },
        onError: () => setErr("Failed to add bill. Please try again."),
      },
    );
  }

  const handleMarkPaid = useCallback(
    (bill: FinanceBill) => {
      setBusyBillId(bill.id);
      markBillPaid.mutate(bill.id, { onSettled: () => setBusyBillId(null) });
    },
    [markBillPaid],
  );

  const renderBill = useCallback(
    ({ item }: { item: FinanceBill }) => (
      <BillCard bill={item} busy={busyBillId === item.id} onMarkPaid={handleMarkPaid} />
    ),
    [busyBillId, handleMarkPaid],
  );

  return (
    <>
      <FlatList
        data={bills}
        keyExtractor={(b) => String(b.id)}
        renderItem={renderBill}
        contentContainerStyle={[styles.content, { gap: 10 }]}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          isPending ? (
            <LoadingCard label="Loading bills…" />
          ) : isError ? (
            <ErrorCard message="Could not load bills." onRetry={refetch} />
          ) : (
            <EmptyCard title="No bills yet." sub="Add your first bill below." />
          )
        }
        ListFooterComponent={
          <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel="Add bill">
            <Plus color={colors.textSecondary} size={16} />
            <Text variant="secondary">Add Bill</Text>
          </Pressable>
        }
      />

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Bill">
        <Field label="Bill name" value={name} onChangeText={setName} placeholder="e.g. Water Bill" />
        <Field label="Amount (PKR)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="0" />
        <Field label="Due date (YYYY-MM-DD, optional)" value={due} onChangeText={setDue} placeholder="2026-07-20" />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Bill" onPress={submit} loading={createBill.isPending} />
      </GlassSheet>
    </>
  );
}

/* -------------------------------- Goals ---------------------------------- */
const GoalCard = memo(function GoalCard({
  goal,
  onContribute,
}: {
  goal: FinanceGoal;
  onContribute: (goal: FinanceGoal) => void;
}) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const target = Number(goal.target) || 0;
  const saved = Number(goal.saved) || 0;
  const pct = target > 0 ? saved / target : 0;
  const c = goal.color === "warning" ? colors.gold : colors.bull;
  return (
    <GlassCard style={{ gap: 8, padding: 14 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <View style={[styles.goalIcon, { borderColor: c + "44", backgroundColor: c + "18" }]}>
          <Target color={c} size={16} />
        </View>
        <Text style={{ fontWeight: "700", flex: 1 }}>{goal.name}</Text>
        <Text style={{ color: c, fontFamily: fonts.mono, fontWeight: "700" }}>{Math.round(pct * 100)}%</Text>
      </View>
      <Text variant="secondary" style={{ fontFamily: fonts.mono, fontSize: 12 }}>
        Target {fmtPKR(target)} · Saved {fmtPKR(saved)}
      </Text>
      <ProgressBar value={Math.min(pct, 1)} color={c} />
      {goal.target_date ? <Text variant="muted">Target date: {goal.target_date}</Text> : null}
      {goal.ai_tip ? (
        <View style={styles.tip}>
          <Sparkles color={colors.ai} size={13} />
          <Text variant="secondary" style={{ flex: 1, fontSize: 12 }}>{goal.ai_tip}</Text>
        </View>
      ) : null}
      <Button
        title="Add Contribution"
        variant="outline"
        icon={<Plus color={colors.textPrimary} size={14} />}
        onPress={() => onContribute(goal)}
      />
    </GlassCard>
  );
});

function Goals() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { data: goals = [], isPending, isError, refetch } = useFinanceGoals();
  const createGoal = useCreateGoal();
  const contributeGoal = useContributeGoal();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [date, setDate] = useState("");
  const [err, setErr] = useState("");
  const [contribGoal, setContribGoal] = useState<FinanceGoal | null>(null);
  const [contribAmount, setContribAmount] = useState("");
  const [contribErr, setContribErr] = useState("");

  function submit() {
    setErr("");
    const num = Number(target);
    if (!name.trim()) return setErr("Please enter a goal name.");
    if (!target || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid target amount.");
    createGoal.mutate(
      {
        name: name.trim(),
        target: num,
        emoji: "🎯",
        color: "bull",
        target_date: date.trim() || undefined,
      },
      {
        onSuccess: () => {
          setName("");
          setTarget("");
          setDate("");
          setOpen(false);
        },
        onError: () => setErr("Could not create goal — you may have reached your plan limit."),
      },
    );
  }

  function submitContribute() {
    setContribErr("");
    const num = Number(contribAmount);
    if (!contribAmount || Number.isNaN(num) || num <= 0) return setContribErr("Please enter a valid amount.");
    if (!contribGoal) return;
    contributeGoal.mutate(
      { id: contribGoal.id, amount: num },
      {
        onSuccess: () => {
          setContribGoal(null);
          setContribAmount("");
        },
        onError: () => setContribErr("Could not add contribution. Please try again."),
      },
    );
  }

  const openContribute = useCallback((goal: FinanceGoal) => {
    setContribGoal(goal);
    setContribAmount("");
    setContribErr("");
  }, []);

  const renderGoal = useCallback(
    ({ item }: { item: FinanceGoal }) => <GoalCard goal={item} onContribute={openContribute} />,
    [openContribute],
  );

  return (
    <>
      <FlatList
        data={goals}
        keyExtractor={(g) => String(g.id)}
        renderItem={renderGoal}
        contentContainerStyle={[styles.content, { gap: 12 }]}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          isPending ? (
            <LoadingCard label="Loading goals…" />
          ) : isError ? (
            <ErrorCard message="Could not load goals." onRetry={refetch} />
          ) : (
            <EmptyCard title="No goals yet." sub="Add your first savings goal to start tracking progress." />
          )
        }
        ListFooterComponent={
          <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel="Add goal">
            <Plus color={colors.textSecondary} size={16} />
            <Text variant="secondary">Add Goal</Text>
          </Pressable>
        }
      />

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Goal">
        <Field label="Goal name" value={name} onChangeText={setName} placeholder="e.g. New Laptop" />
        <Field label="Target amount (PKR)" value={target} onChangeText={setTarget} keyboardType="numeric" placeholder="0" />
        <Field label="Target date (optional)" value={date} onChangeText={setDate} placeholder="e.g. Dec 2026" />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Goal" onPress={submit} loading={createGoal.isPending} />
      </GlassSheet>

      <GlassSheet
        open={contribGoal != null}
        onClose={() => setContribGoal(null)}
        title={`Add Contribution${contribGoal ? ` — ${contribGoal.name}` : ""}`}
      >
        <Field label="Amount (PKR)" value={contribAmount} onChangeText={setContribAmount} keyboardType="numeric" placeholder="0" autoFocus />
        {contribErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{contribErr}</Text> : null}
        <Button title="Add Contribution" onPress={submitContribute} loading={contributeGoal.isPending} />
      </GlassSheet>
    </>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: color }} />
      <Text variant="muted">{label}</Text>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    header: { paddingHorizontal: 16, paddingTop: 16, gap: 16 },
    content: { padding: 16, paddingBottom: 28, gap: 16 },
    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    grid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
    kpi: { width: "47%", flexGrow: 1, padding: 14 },
    iconChip: { width: 34, height: 34, borderRadius: 10, alignItems: "center", justifyContent: "center" },
    search: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface, borderRadius: radii.btn, paddingHorizontal: 12, minHeight: 44 },
    txn: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 12, paddingVertical: 10 },
    dot: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
    monthNav: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 20 },
    tip: { flexDirection: "row", gap: 8, borderLeftWidth: 2, borderLeftColor: c.ai, backgroundColor: c.aiTint, padding: 8, borderRadius: 6 },
    billRow: { flexDirection: "row", alignItems: "center", gap: 10, padding: 14 },
    avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: c.elevated, alignItems: "center", justifyContent: "center" },
    statusBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
    checkBtn: { width: 32, height: 32, borderRadius: 16, borderWidth: 1, borderColor: c.bull, alignItems: "center", justifyContent: "center" },
    dashed: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 8, borderWidth: 1, borderStyle: "dashed", borderColor: c.border, borderRadius: radii.btn, paddingVertical: 14 },
    goalIcon: { width: 34, height: 34, borderRadius: 8, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  });
