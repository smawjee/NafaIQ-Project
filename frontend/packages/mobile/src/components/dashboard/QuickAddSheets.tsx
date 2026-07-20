// Quick-add glass sheets launched from the dashboard action row. Transaction
// posts to the finance API (/api/finance/transactions); Alert posts to
// /api/alerts (mirrors web QuickAddAlertModal, same type→meta mapping as
// src/app/alerts.tsx). Add Holding posts to the portfolio API (mirrors web
// QuickAddHoldingModal — auto-creates a "Main" portfolio if none).
import { type ReactNode, useMemo, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { GlassPrimaryButton } from "@/components/glass/GlassButtons";
import { GlassSheet } from "@/components/glass/GlassSheet";
import { Field } from "@/components/Modal";
import { Text } from "@/components/ui";
import { ChipRow, Segmented } from "@/components/ui/controls";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { type AlertEventType, useCreateAlert } from "@/hooks/queries/use-alerts";
import { useCreatePriceAlert } from "@/hooks/queries/use-price-alerts";
import {
  useCreateTransaction,
  useFinanceBills,
  useFinanceBudgets,
  useFinanceGoals,
} from "@/hooks/queries/use-finance";
import { useAddHolding, useCreatePortfolio, usePortfolioList } from "@/hooks/queries/use-portfolio";
import { CalendarClock, Check, type LucideIcon, Plus, Target, TrendingUp, Wallet } from "@/lib/icons";

export type QuickAdd = null | "tx" | "alert" | "holding";

const TX_CATEGORIES = ["Food & Dining", "Groceries", "Transport", "Utilities", "Shopping", "Subscriptions", "Savings"];
const TX_ACCOUNTS = ["HBL Current", "Meezan Debit", "Easypaisa", "Meezan Savings"];

type AlertKind = "Stock Price" | "Bill Reminder" | "Budget" | "Goal Milestone";
const ALERT_KINDS: { key: AlertKind; icon: LucideIcon }[] = [
  { key: "Stock Price", icon: TrendingUp },
  { key: "Bill Reminder", icon: CalendarClock },
  { key: "Budget", icon: Wallet },
  { key: "Goal Milestone", icon: Target },
];
// Curated symbol shortlist — mirrors web dashboard.data ALERT_STOCKS.
const ALERT_STOCKS = ["HBL", "ENGRO", "LUCK", "OGDC"];
const BILL_TIMING = ["1 day before", "3 days before", "On due date"];
const BUDGET_THRESHOLDS = ["50%", "80%", "90%", "100%"];
const GOAL_MILESTONES = ["25%", "50%", "75%", "100%"];

export function QuickAddSheets({
  which,
  onClose,
  onToast,
}: {
  which: QuickAdd;
  onClose: () => void;
  onToast: (msg: string) => void;
}) {
  return (
    <>
      <TransactionSheet open={which === "tx"} onClose={onClose} onToast={onToast} />
      <HoldingSheet open={which === "holding"} onClose={onClose} onToast={onToast} />
      <AlertSheet open={which === "alert"} onClose={onClose} onToast={onToast} />
    </>
  );
}

function HoldingSheet({ open, onClose, onToast }: { open: boolean; onClose: () => void; onToast: (m: string) => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [err, setErr] = useState("");

  // Same flow as web's QuickAddHoldingModal: POST to the user's first
  // portfolio, auto-creating "Main" when they have none yet.
  const { data: portfolios } = usePortfolioList(open);
  const portfolioId = portfolios?.[0]?.id ?? null;
  const addHoldingApi = useAddHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();
  const saving = addHoldingApi.isPending || createPortfolio.isPending;

  function submit() {
    setErr("");
    const sym = symbol.trim().toUpperCase();
    const sh = Math.abs(Number(shares.replace(/[^0-9.]/g, "")));
    const pr = Math.abs(Number(price.replace(/[^0-9.]/g, "")));
    if (sym.length < 2) return setErr("Enter a stock symbol");
    if (!sh) return setErr("Enter the number of shares");
    if (!pr) return setErr("Enter a valid buy price");
    // avg_cost is Numeric(12,2) on the backend — round to stored precision.
    const avg_cost = Math.round(pr * 100) / 100;
    const onError = () => setErr("Could not add the holding. Please try again.");
    const onSuccess = () => {
      setSymbol(""); setShares(""); setPrice(""); setErr("");
      onClose();
      onToast("Holding added");
    };
    if (portfolioId) {
      addHoldingApi.mutate({ symbol: sym, shares: sh, avg_cost }, { onSuccess, onError });
    } else {
      createPortfolio.mutate("Main", {
        onSuccess: (p) =>
          addHoldingApi.mutate(
            { portfolioId: p.id, symbol: sym, shares: sh, avg_cost },
            { onSuccess, onError },
          ),
        onError,
      });
    }
  }

  return (
    <GlassSheet open={open} onClose={onClose} title="Add Holding">
      <Field label="" accessibilityLabel="Stock symbol" value={symbol} onChangeText={setSymbol} placeholder="Stock symbol (e.g. HBL)" autoCapitalize="characters" autoCorrect={false} />
      <Field label="" accessibilityLabel="Shares" value={shares} onChangeText={setShares} placeholder="Shares" keyboardType="numeric" inputMode="numeric" />
      <Field label="" accessibilityLabel="Buy price in rupees" value={price} onChangeText={setPrice} placeholder="Buy price (PKR)" keyboardType="numeric" inputMode="numeric" />
      {err ? <Text style={styles.err}>{err}</Text> : null}
      <GlassPrimaryButton label="Add Holding" loading={saving} icon={<Plus color={colors.primaryForeground} size={16} />} onPress={submit} />
    </GlassSheet>
  );
}

function TransactionSheet({ open, onClose, onToast }: { open: boolean; onClose: () => void; onToast: (m: string) => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [kind, setKind] = useState("expense");
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(TX_CATEGORIES[0]);
  const [account, setAccount] = useState(TX_ACCOUNTS[0]);
  const [err, setErr] = useState("");

  const isIncome = kind === "income";
  const createTransaction = useCreateTransaction();

  function submit() {
    setErr("");
    const amt = Math.abs(Number(amount.replace(/[^0-9.]/g, "")));
    if (merchant.trim().length < 2) return setErr("Enter a merchant / source");
    if (!amt) return setErr("Enter a valid amount");
    // POST /api/finance/transactions — same contract as the web dashboard modal.
    createTransaction.mutate(
      {
        merchant: merchant.trim(),
        amount: amt,
        transaction_type: isIncome ? "income" : "expense",
        category: isIncome ? "Income" : category,
        transaction_date: new Date().toISOString(),
        source: account,
        note: null,
      },
      {
        onSuccess: () => {
          reset();
          onClose();
          onToast("Transaction added");
        },
        onError: () => setErr("Could not add the transaction. Please try again."),
      },
    );
  }
  function reset() {
    setKind("expense"); setMerchant(""); setAmount(""); setCategory(TX_CATEGORIES[0]); setAccount(TX_ACCOUNTS[0]); setErr("");
  }

  return (
    <GlassSheet open={open} onClose={onClose} title="Add Transaction">
      <ChipRow options={["expense", "income"]} value={kind} onChange={setKind} />
      <Field label="Merchant / Source" value={merchant} onChangeText={setMerchant} placeholder="e.g. Cheezious" />
      <Field
        label="Amount (PKR)"
        value={amount}
        onChangeText={setAmount}
        placeholder="0"
        keyboardType="numeric"
        inputMode="numeric"
      />
      {!isIncome && (
        <View style={{ gap: 4 }}>
          <Text variant="secondary">Category</Text>
          <ChipRow options={TX_CATEGORIES} value={category} onChange={setCategory} />
        </View>
      )}
      <View style={{ gap: 4 }}>
        <Text variant="secondary">Account</Text>
        <ChipRow options={TX_ACCOUNTS} value={account} onChange={setAccount} />
      </View>
      {err ? <Text style={styles.err}>{err}</Text> : null}
      <GlassPrimaryButton label="Add Transaction" loading={createTransaction.isPending} icon={<Plus color={colors.primaryForeground} size={16} />} onPress={submit} />
    </GlassSheet>
  );
}

function AlertSheet({ open, onClose, onToast }: { open: boolean; onClose: () => void; onToast: (m: string) => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  // Live bill/budget/goal targets — the same finance queries the web modal
  // reads, fetched only while the sheet is open.
  const { data: billsData } = useFinanceBills(open);
  const { data: budgetsData } = useFinanceBudgets(open);
  const { data: goalsData } = useFinanceGoals(open);
  const billOptions = useMemo(() => (billsData ?? []).map((b) => b.name), [billsData]);
  const budgetOptions = useMemo(() => (budgetsData ?? []).map((b) => b.category), [budgetsData]);
  const goalOptions = useMemo(() => (goalsData ?? []).map((g) => g.name), [goalsData]);

  const createAlert = useCreateAlert();
  const createPriceAlert = useCreatePriceAlert();
  const [kind, setKind] = useState<AlertKind>("Stock Price");
  const [symbol, setSymbol] = useState(ALERT_STOCKS[0]);
  const [direction, setDirection] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState("");
  const [timing, setTiming] = useState(BILL_TIMING[0]);
  const [category, setCategory] = useState("");
  const [threshold, setThreshold] = useState("80%");
  const [goal, setGoal] = useState("");
  const [milestone, setMilestone] = useState("50%");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [err, setErr] = useState("");

  // Options load async — fall back to the first fetched row until a pick is made.
  const selectedBill = bill || billOptions[0] || "";
  const selectedCategory = category || budgetOptions[0] || "";
  const selectedGoal = goal || goalOptions[0] || "";

  // Same title/type/meta mapping as src/app/alerts.tsx handleCreate (web parity).
  function build(): { title: string; type: AlertEventType; meta: Record<string, unknown> } | null {
    if (kind === "Stock Price") {
      const p = Math.abs(Number(price.replace(/[^0-9.]/g, "")));
      if (!p) { setErr("Enter a target price"); return null; }
      return {
        title: `${symbol} ${direction.toLowerCase()} PKR ${p}`,
        type: "stock_price",
        meta: { symbol, direction: direction.toLowerCase(), price: p },
      };
    }
    if (kind === "Bill Reminder") {
      if (!selectedBill) { setErr("Pick a bill"); return null; }
      return { title: `${selectedBill} — ${timing}`, type: "bill", meta: { bill: selectedBill, timing } };
    }
    if (kind === "Budget") {
      if (!selectedCategory) { setErr("Pick a budget category"); return null; }
      const pct = threshold.replace("%", "");
      return {
        title: `${selectedCategory} at ${pct}% of budget`,
        type: "budget",
        meta: { category: selectedCategory, threshold: pct },
      };
    }
    if (!selectedGoal) { setErr("Pick a goal"); return null; }
    const pct = milestone.replace("%", "");
    return { title: `${selectedGoal} ${pct}% reached`, type: "goal", meta: { goal: selectedGoal, milestone: pct } };
  }

  function submit() {
    setErr("");
    const done = (msg: string) => {
      setPrice("");
      setErr("");
      onClose();
      onToast(msg);
    };
    const fail = (e: unknown) =>
      setErr(e instanceof Error ? e.message : "Could not create the alert. Please try again.");

    // Stock price → dedicated price_alerts (channels persist); the generic
    // app-alert types (bill/budget/goal) have no channel field.
    if (kind === "Stock Price") {
      if (!push && !email) return setErr("Choose at least one channel");
      const p = Math.abs(Number(price.replace(/[^0-9.]/g, "")));
      if (!p) return setErr("Enter a target price");
      createPriceAlert.mutate(
        {
          symbol,
          condition: direction === "Above" ? "above" : "below",
          price: p,
          one_time: false,
          notify_push: push,
          notify_email: email,
        },
        { onSuccess: () => done("Price alert created"), onError: fail },
      );
      return;
    }

    const built = build();
    if (!built) return;
    createAlert.mutate(built, {
      onSuccess: () => done("Alert created"),
      onError: fail,
    });
  }

  return (
    <GlassSheet open={open} onClose={onClose} title="Add Alert">
      <View style={styles.typeGrid}>
        {ALERT_KINDS.map((k) => (
          <TypeCard key={k.key} icon={k.icon} label={k.key} active={kind === k.key} onPress={() => { setKind(k.key); setErr(""); }} />
        ))}
      </View>

      {kind === "Stock Price" && (
        <>
          <SelectRow label="Symbol"><ChipRow options={ALERT_STOCKS} value={symbol} onChange={setSymbol} /></SelectRow>
          <SelectRow label="Condition"><Segmented options={["Above", "Below"]} value={direction} onChange={setDirection} /></SelectRow>
          <Field label="Target price (PKR)" value={price} onChangeText={setPrice} placeholder="0" keyboardType="numeric" inputMode="numeric" />
        </>
      )}
      {kind === "Bill Reminder" && (
        <>
          <SelectRow label="Bill">
            {billOptions.length === 0 ? (
              <Text variant="muted">No bills yet. Add bills from Finance first.</Text>
            ) : (
              <ChipRow options={billOptions} value={selectedBill} onChange={setBill} />
            )}
          </SelectRow>
          <SelectRow label="Remind me"><ChipRow options={BILL_TIMING} value={timing} onChange={setTiming} /></SelectRow>
        </>
      )}
      {kind === "Budget" && (
        <>
          <SelectRow label="Category">
            {budgetOptions.length === 0 ? (
              <Text variant="muted">No budgets yet. Add budgets from Finance first.</Text>
            ) : (
              <ChipRow options={budgetOptions} value={selectedCategory} onChange={setCategory} />
            )}
          </SelectRow>
          <SelectRow label="Threshold"><Segmented options={BUDGET_THRESHOLDS} value={threshold} onChange={setThreshold} /></SelectRow>
        </>
      )}
      {kind === "Goal Milestone" && (
        <>
          <SelectRow label="Goal">
            {goalOptions.length === 0 ? (
              <Text variant="muted">No goals yet. Add goals from Finance first.</Text>
            ) : (
              <ChipRow options={goalOptions} value={selectedGoal} onChange={setGoal} />
            )}
          </SelectRow>
          <SelectRow label="Milestone"><Segmented options={GOAL_MILESTONES} value={milestone} onChange={setMilestone} /></SelectRow>
        </>
      )}

      {kind === "Stock Price" ? (
        <View style={styles.channels}>
          <Checkbox label="Push" checked={push} onToggle={() => setPush((v) => !v)} />
          <Checkbox label="Email" checked={email} onToggle={() => setEmail((v) => !v)} />
        </View>
      ) : null}

      {err ? <Text style={styles.err}>{err}</Text> : null}
      <GlassPrimaryButton label="Create Alert" loading={createAlert.isPending || createPriceAlert.isPending} icon={<Plus color={colors.primaryForeground} size={16} />} onPress={submit} />
    </GlassSheet>
  );
}

function TypeCard({ icon: Icon, label, active, onPress }: { icon: LucideIcon; label: string; active: boolean; onPress: () => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <Pressable style={styles.typeCardWrap} onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: active }} accessibilityLabel={label}>
      <GlassCard radius={14} intensity={active ? 26 : 16} style={[styles.typeCard, active && { borderColor: colors.primary }]}>
        {active && <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.primary + "1c" }]} pointerEvents="none" />}
        <Icon color={active ? colors.primary : colors.textSecondary} size={20} />
        <Text style={{ fontSize: 12, fontWeight: "600", textAlign: "center", marginTop: 6, color: active ? colors.primary : colors.textSecondary }}>{label}</Text>
      </GlassCard>
    </Pressable>
  );
}

function SelectRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={{ gap: 6 }}>
      <Text variant="secondary" style={{ fontSize: 13 }}>{label}</Text>
      {children}
    </View>
  );
}

function Checkbox({ label, checked, onToggle }: { label: string; checked: boolean; onToggle: () => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <Pressable style={styles.checkRow} onPress={onToggle} hitSlop={8} accessibilityRole="checkbox" accessibilityState={{ checked }} accessibilityLabel={label}>
      <View style={[styles.checkBox, checked && { backgroundColor: colors.primary, borderColor: colors.primary }]}>
        {checked && <Check color={colors.primaryForeground} size={13} strokeWidth={3} />}
      </View>
      <Text style={{ fontSize: 14, fontFamily: fonts.sans }}>{label}</Text>
    </Pressable>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    err: { color: c.bear, fontSize: 12 },
    typeGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: 8 },
    typeCardWrap: { width: "48.5%" },
    typeCard: { height: 76, alignItems: "center", justifyContent: "center", padding: 8, borderColor: c.border },
    channels: { flexDirection: "row", gap: 24, marginTop: 2 },
    checkRow: { flexDirection: "row", alignItems: "center", gap: 8 },
    checkBox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1.5, borderColor: c.borderHover, alignItems: "center", justifyContent: "center" },
  });
