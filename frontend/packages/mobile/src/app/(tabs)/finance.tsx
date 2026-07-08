// Personal Finance (`/finance`). Mirrors web `/finance`: tabbed Overview /
// Transactions / Budgets / Bills / Goals. Demo data is small & fixed, so lists
// use .map inside a ScrollView (swap to SectionList/FlatList for live data).
import { useMemo, useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, TextInput, useWindowDimensions, View } from "react-native";
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
import { budgetsActions, monthKeyFor, useBudgets } from "@/hooks/use-budgets-store";
import { useTheme } from "@/hooks/use-theme";
import { financeActions, useFinanceStore } from "@/hooks/use-finance-store";
import { fmtPKR } from "@nafaiq/shared";
import { type Goal, INCOME_EXPENSE } from "@nafaiq/shared";
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

export default function FinanceScreen() {
  const [tab, setTab] = useState("Overview");
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <GlassScreen>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <Text variant="display" style={{ fontFamily: AVENIR }}>Personal Finance</Text>
          <Segmented options={TABS} value={tab} onChange={setTab} />
          {tab === "Overview" && <Overview />}
          {tab === "Transactions" && <Transactions />}
          {tab === "Budgets" && <Budgets />}
          {tab === "Bills" && <Bills />}
          {tab === "Goals" && <Goals />}
        </ScrollView>
      </SafeAreaView>
    </GlassScreen>
  );
}

/* ------------------------------- Overview -------------------------------- */
function Kpi({
  icon,
  label,
  value,
  color,
  sub,
  spark,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
  sub?: string;
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
        {sub ? <Text variant="muted" style={{ flex: 1 }}>{sub}</Text> : <View style={{ flex: 1 }} />}
        {spark ? <Sparkline data={spark} width={48} height={20} color={color} /> : null}
      </View>
    </GlassCard>
  );
}

function Overview() {
  const { width } = useWindowDimensions();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={{ gap: 16 }}>
      <View style={styles.grid}>
        <Kpi icon={<ArrowUpRight color={colors.bull} size={18} />} label="Monthly Income" value={fmtPKR(47500)} color={colors.bull} sub="+PKR 2,500 vs last" spark={[43000, 45000, 47500]} />
        <Kpi icon={<ArrowDownRight color={colors.bear} size={18} />} label="Total Expenses" value={fmtPKR(18675)} color={colors.bear} sub="-12% vs last" spark={[22000, 21200, 18675]} />
        <Kpi icon={<PiggyBank color={colors.ai} size={18} />} label="Net Savings" value={fmtPKR(28825)} color={colors.ai} sub="+PKR 4,825" />
        <Kpi icon={<Percent color={colors.warning} size={18} />} label="Savings Rate" value="60.7%" color={colors.warning} sub="Goal: 65%" />
      </View>

      <GlassCard style={{ gap: 12, padding: 16 }}>
        <View style={styles.between}>
          <Text variant="title">6-Month Overview</Text>
          <View style={{ flexDirection: "row", gap: 12 }}>
            <Legend color={colors.bull} label="In" />
            <Legend color={colors.bear} label="Out" />
          </View>
        </View>
        <IncomeExpenseChart data={INCOME_EXPENSE} width={width - 64} />
        <Text variant="muted" style={{ textAlign: "center" }}>
          Saved PKR 1,72,950 over 6 months
        </Text>
      </GlassCard>
    </View>
  );
}

/* ----------------------------- Transactions ------------------------------ */
function Transactions() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { transactions } = useFinanceStore();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [account, setAccount] = useState(ACCOUNTS[0]);
  const [err, setErr] = useState("");

  const grouped = useMemo(() => {
    const filtered = transactions.filter((tx) =>
      (tx.merchant + tx.category + tx.account).toLowerCase().includes(q.toLowerCase()),
    );
    return filtered.reduce<Record<string, typeof transactions>>((acc, tx) => {
      (acc[tx.date] ??= []).push(tx);
      return acc;
    }, {});
  }, [q, transactions]);

  function submit() {
    setErr("");
    const num = Number(amount);
    if (!merchant.trim()) return setErr("Please enter a merchant name.");
    if (!amount || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid amount.");
    financeActions.addTransaction({
      merchant: merchant.trim(),
      category: kind === "income" ? "Income" : category,
      account,
      amount: kind === "income" ? num : -num,
    });
    setMerchant("");
    setAmount("");
    setKind("expense");
    setOpen(false);
  }

  return (
    <View style={{ gap: 16 }}>
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
      {Object.entries(grouped).map(([date, items]) => (
        <View key={date} style={{ gap: 6 }}>
          <Text variant="muted" style={{ fontWeight: "600" }}>{date}</Text>
          <GlassCard style={{ gap: 0, padding: 0 }}>
            {items.map((tx, i) => (
              <View key={i} style={[styles.txn, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
                <View style={[styles.dot, { backgroundColor: (CAT_COLOR[tx.category] ?? "#6b7280") + "33" }]}>
                  <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: CAT_COLOR[tx.category] ?? "#6b7280" }} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text variant="body">{tx.merchant}</Text>
                  <Text variant="muted">{tx.category} · {tx.account}</Text>
                </View>
                <Text style={{ color: tx.amount >= 0 ? colors.bull : colors.bear, fontFamily: fonts.mono, fontSize: 13 }}>
                  {tx.amount >= 0 ? "+" : "-"}
                  {fmtPKR(Math.abs(tx.amount))}
                </Text>
              </View>
            ))}
          </GlassCard>
        </View>
      ))}

      <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button">
        <Plus color={colors.textSecondary} size={16} />
        <Text variant="secondary">Add Transaction</Text>
      </Pressable>

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Transaction">
        <ChipRow options={["expense", "income"]} value={kind} onChange={(v) => setKind(v as "expense" | "income")} />
        <Field label="Merchant" value={merchant} onChangeText={setMerchant} placeholder="e.g. Imtiaz Super Market" />
        <Field label="Amount (PKR)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="0" />
        {kind === "expense" ? <ChipRow options={CATEGORIES} value={category} onChange={setCategory} /> : null}
        <ChipRow options={ACCOUNTS} value={account} onChange={setAccount} />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Transaction" onPress={submit} />
      </GlassSheet>
    </View>
  );
}

/* ------------------------------- Budgets --------------------------------- */
function Budgets() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [offset, setOffset] = useState(0);
  const budgetMap = useBudgets();
  const monthKey = monthKeyFor(offset);
  const budgets = budgetMap[monthKey] ?? [];
  const now = new Date();
  const prevLabel = MONTHS[new Date(now.getFullYear(), now.getMonth() + offset - 1, 1).getMonth()];
  const nextLabel = MONTHS[new Date(now.getFullYear(), now.getMonth() + offset + 1, 1).getMonth()];

  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [limit, setLimit] = useState("");
  const [err, setErr] = useState("");

  function submit() {
    setErr("");
    const num = Number(limit);
    if (!limit || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid monthly limit.");
    budgetsActions.addBudget(monthKey, { category, spent: 0, limit: num });
    setCategory(CATEGORIES[0]);
    setLimit("");
    setOpen(false);
  }

  return (
    <View style={{ gap: 12 }}>
      <View style={styles.monthNav}>
        <Pressable onPress={() => setOffset((o) => o - 1)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Previous month">
          <Text style={{ color: colors.textSecondary }}>‹ {prevLabel}</Text>
        </Pressable>
        <Text style={{ fontWeight: "700" }}>{monthKey}</Text>
        <Pressable onPress={() => setOffset((o) => o + 1)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Next month">
          <Text style={{ color: colors.textSecondary }}>{nextLabel} ›</Text>
        </Pressable>
      </View>

      {budgets.length === 0 ? (
        <GlassCard style={{ padding: 22, alignItems: "center", gap: 4 }}>
          <Text variant="secondary" style={{ textAlign: "center" }}>No budgets set for {monthKey}.</Text>
          <Text variant="muted" style={{ textAlign: "center" }}>Plan ahead — add a budget for this month.</Text>
        </GlassCard>
      ) : (
        budgets.map((b) => {
          const pct = b.spent / b.limit;
          const over = b.spent > b.limit;
          const c = over ? colors.bear : pct >= 0.8 ? colors.warning : colors.bull;
          return (
            <GlassCard key={b.category} style={{ gap: 8, padding: 14 }}>
              <View style={styles.between}>
                <Text style={{ fontWeight: "600" }}>{b.category}</Text>
                <Text style={{ color: over ? colors.bear : colors.textSecondary, fontFamily: fonts.mono, fontSize: 12 }}>
                  {fmtPKR(b.spent)} / {fmtPKR(b.limit)}
                </Text>
              </View>
              <ProgressBar value={pct} color={c} />
              {b.tip ? (
                <View style={styles.tip}>
                  <Lightbulb color={colors.ai} size={13} />
                  <Text variant="secondary" style={{ flex: 1, fontSize: 12 }}>{b.tip}</Text>
                </View>
              ) : null}
            </GlassCard>
          );
        })
      )}

      <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button">
        <Plus color={colors.textSecondary} size={16} />
        <Text variant="secondary">Add Budget</Text>
      </Pressable>

      <GlassSheet open={open} onClose={() => setOpen(false)} title={`Add Budget — ${monthKey}`}>
        <View style={{ gap: 4 }}>
          <Text variant="secondary">Category</Text>
          <ChipRow options={CATEGORIES} value={category} onChange={setCategory} />
        </View>
        <Field label="Monthly limit (PKR)" value={limit} onChangeText={setLimit} keyboardType="numeric" placeholder="0" />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Budget" onPress={submit} />
      </GlassSheet>
    </View>
  );
}

/* -------------------------------- Bills ---------------------------------- */
function Bills() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { bills } = useFinanceStore();
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
    financeActions.addBill({ name: name.trim(), amount: num, due: due.trim() || "—", status: "UPCOMING" });
    setName("");
    setAmount("");
    setDue("");
    setOpen(false);
  }

  return (
    <View style={{ gap: 10 }}>
      {bills.map((b) => (
        <GlassCard key={b.name} style={styles.billRow}>
          <View style={styles.avatar}>
            <Text style={{ fontWeight: "700", color: colors.textSecondary }}>{b.name[0]}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }} numberOfLines={1}>{b.name}</Text>
            <Text variant="muted">Due {b.due}</Text>
          </View>
          <View style={{ alignItems: "flex-end", gap: 5 }}>
            <Text variant="mono" style={{ fontSize: 13 }}>{fmtPKR(b.amount)}</Text>
            <View style={[styles.statusBadge, { backgroundColor: b.status === "DUE SOON" ? colors.warning + "33" : colors.elevated }]}>
              <Text style={{ fontSize: 10, fontWeight: "700", color: b.status === "DUE SOON" ? colors.warning : colors.textSecondary }}>
                {b.status}
              </Text>
            </View>
          </View>
          <Pressable
            style={styles.checkBtn}
            onPress={() => financeActions.markBillPaid(b.name)}
            accessibilityRole="button"
            accessibilityLabel={`Mark ${b.name} paid`}
          >
            <Check color={colors.bull} size={16} />
          </Pressable>
        </GlassCard>
      ))}
      <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button">
        <Plus color={colors.textSecondary} size={16} />
        <Text variant="secondary">Add Bill</Text>
      </Pressable>

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Bill">
        <Field label="Bill name" value={name} onChangeText={setName} placeholder="e.g. Water Bill" />
        <Field label="Amount (PKR)" value={amount} onChangeText={setAmount} keyboardType="numeric" placeholder="0" />
        <Field label="Due (e.g. Jun 20)" value={due} onChangeText={setDue} placeholder="Jun 20" />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Bill" onPress={submit} />
      </GlassSheet>
    </View>
  );
}

/* -------------------------------- Goals ---------------------------------- */
function Goals() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { goals } = useFinanceStore();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [date, setDate] = useState("");
  const [err, setErr] = useState("");
  const [contribGoal, setContribGoal] = useState<string | null>(null);
  const [contribAmount, setContribAmount] = useState("");
  const [contribErr, setContribErr] = useState("");

  function submit() {
    setErr("");
    const num = Number(target);
    if (!name.trim()) return setErr("Please enter a goal name.");
    if (!target || Number.isNaN(num) || num <= 0) return setErr("Please enter a valid target amount.");
    const goal: Goal = {
      emoji: "🎯",
      name: name.trim(),
      target: num,
      saved: 0,
      color: "bull",
      date: date.trim() || undefined,
      ai: "New goal created. Start contributing to track your progress.",
    };
    financeActions.addGoal(goal);
    setName("");
    setTarget("");
    setDate("");
    setOpen(false);
  }

  function submitContribute() {
    setContribErr("");
    const num = Number(contribAmount);
    if (!contribAmount || Number.isNaN(num) || num <= 0) return setContribErr("Please enter a valid amount.");
    if (contribGoal) financeActions.contributeToGoal(contribGoal, num);
    setContribGoal(null);
    setContribAmount("");
  }

  return (
    <View style={{ gap: 12 }}>
      {goals.map((g) => {
        const pct = g.saved / g.target;
        const c = g.color === "warning" ? colors.gold : colors.bull;
        return (
          <GlassCard key={g.name} style={{ gap: 8, padding: 14 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <View style={[styles.goalIcon, { borderColor: c + "44", backgroundColor: c + "18" }]}>
                <Target color={c} size={16} />
              </View>
              <Text style={{ fontWeight: "700", flex: 1 }}>{g.name}</Text>
              <Text style={{ color: c, fontFamily: fonts.mono, fontWeight: "700" }}>{Math.round(pct * 100)}%</Text>
            </View>
            <Text variant="secondary" style={{ fontFamily: fonts.mono, fontSize: 12 }}>
              Target {fmtPKR(g.target)} · Saved {fmtPKR(g.saved)}
            </Text>
            <ProgressBar value={pct} color={c} />
            {g.date ? <Text variant="muted">Target date: {g.date}</Text> : null}
            <View style={styles.tip}>
              <Sparkles color={colors.ai} size={13} />
              <Text variant="secondary" style={{ flex: 1, fontSize: 12 }}>{g.ai}</Text>
            </View>
            <Button
              title="Add Contribution"
              variant="outline"
              icon={<Plus color={colors.textPrimary} size={14} />}
              onPress={() => {
                setContribGoal(g.name);
                setContribAmount("");
                setContribErr("");
              }}
            />
          </GlassCard>
        );
      })}
      <Pressable style={styles.dashed} onPress={() => setOpen(true)} accessibilityRole="button">
        <Plus color={colors.textSecondary} size={16} />
        <Text variant="secondary">Add Goal</Text>
      </Pressable>

      <GlassSheet open={open} onClose={() => setOpen(false)} title="Add Goal">
        <Field label="Goal name" value={name} onChangeText={setName} placeholder="e.g. New Laptop" />
        <Field label="Target amount (PKR)" value={target} onChangeText={setTarget} keyboardType="numeric" placeholder="0" />
        <Field label="Target date (optional)" value={date} onChangeText={setDate} placeholder="e.g. Dec 2026" />
        {err ? <Text style={{ color: colors.bear, fontSize: 12 }}>{err}</Text> : null}
        <Button title="Add Goal" onPress={submit} />
      </GlassSheet>

      <GlassSheet
        open={contribGoal != null}
        onClose={() => setContribGoal(null)}
        title={`Add Contribution${contribGoal ? ` — ${contribGoal}` : ""}`}
      >
        <Field label="Amount (PKR)" value={contribAmount} onChangeText={setContribAmount} keyboardType="numeric" placeholder="0" autoFocus />
        {contribErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{contribErr}</Text> : null}
        <Button title="Add Contribution" onPress={submitContribute} />
      </GlassSheet>
    </View>
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
