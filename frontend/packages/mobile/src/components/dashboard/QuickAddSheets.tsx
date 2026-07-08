// Quick-add glass sheets launched from the dashboard action row. Transaction and
// Alert write straight to the persisted finance store (financeActions), matching
// the web app's dashboard modals. (Add Holding navigates to Portfolio, where
// holdings are managed.)
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
import { financeActions, useFinanceStore } from "@/hooks/use-finance-store";
import { holdingsActions } from "@/hooks/use-holdings-store";
import { STOCK_LIST, STOCKS } from "@nafaiq/shared";
import { SPENDING } from "@nafaiq/shared";
import { CalendarClock, Check, type LucideIcon, Plus, Target, TrendingUp, Wallet } from "@/lib/icons";

export type QuickAdd = null | "tx" | "alert" | "holding";

const TX_CATEGORIES = ["Food & Dining", "Groceries", "Transport", "Utilities", "Shopping", "Subscriptions", "Savings"];
const TX_ACCOUNTS = ["HBL Current", "Meezan Debit", "Easypaisa", "Meezan Savings"];

type AlertKind = "Stock Price" | "Bill Reminder" | "Budget" | "Goal Milestone";
const ALERT_KINDS: { key: AlertKind; icon: LucideIcon; emoji: string }[] = [
  { key: "Stock Price", icon: TrendingUp, emoji: "📈" },
  { key: "Bill Reminder", icon: CalendarClock, emoji: "🔔" },
  { key: "Budget", icon: Wallet, emoji: "💸" },
  { key: "Goal Milestone", icon: Target, emoji: "🎯" },
];
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

  function submit() {
    const sym = symbol.trim().toUpperCase();
    const sh = Math.abs(Number(shares.replace(/[^0-9.]/g, "")));
    const pr = Math.abs(Number(price.replace(/[^0-9.]/g, "")));
    if (sym.length < 2) return setErr("Enter a stock symbol");
    if (!sh) return setErr("Enter the number of shares");
    if (!pr) return setErr("Enter a valid buy price");
    const stock = STOCKS[sym];
    // Reflect in the portfolio…
    holdingsActions.addHolding({
      ticker: sym,
      sector: stock?.sector ?? "Other",
      shares: sh,
      avgCost: pr,
      current: stock?.price ?? pr,
      signal: stock?.signal ?? "HOLD",
    });
    // …and record the purchase as an expense in Finance.
    financeActions.addTransaction({
      merchant: `Bought ${sh} ${sym}`,
      category: "Savings",
      account: "HBL Current",
      amount: -(sh * pr),
    });
    setSymbol(""); setShares(""); setPrice(""); setErr("");
    onClose();
    onToast("Holding added");
  }

  return (
    <GlassSheet open={open} onClose={onClose} title="Add Holding">
      <Field label="" accessibilityLabel="Stock symbol" value={symbol} onChangeText={setSymbol} placeholder="Stock symbol (e.g. HBL)" autoCapitalize="characters" autoCorrect={false} />
      <Field label="" accessibilityLabel="Shares" value={shares} onChangeText={setShares} placeholder="Shares" keyboardType="numeric" inputMode="numeric" />
      <Field label="" accessibilityLabel="Buy price in rupees" value={price} onChangeText={setPrice} placeholder="Buy price (PKR)" keyboardType="numeric" inputMode="numeric" />
      {err ? <Text style={styles.err}>{err}</Text> : null}
      <GlassPrimaryButton label="Add Holding" icon={<Plus color={colors.primaryForeground} size={16} />} onPress={submit} />
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

  function submit() {
    const amt = Math.abs(Number(amount.replace(/[^0-9.]/g, "")));
    if (merchant.trim().length < 2) return setErr("Enter a merchant / source");
    if (!amt) return setErr("Enter a valid amount");
    financeActions.addTransaction({
      merchant: merchant.trim(),
      category: isIncome ? "Income" : category,
      account,
      amount: isIncome ? amt : -amt,
    });
    reset();
    onClose();
    onToast("Transaction added");
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
      <GlassPrimaryButton label="Add Transaction" icon={<Plus color={colors.primaryForeground} size={16} />} onPress={submit} />
    </GlassSheet>
  );
}

function AlertSheet({ open, onClose, onToast }: { open: boolean; onClose: () => void; onToast: (m: string) => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { goals, bills } = useFinanceStore();
  const [kind, setKind] = useState<AlertKind>("Stock Price");
  const [symbol, setSymbol] = useState(STOCK_LIST[0].ticker);
  const [direction, setDirection] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState(bills[0]?.name ?? "");
  const [timing, setTiming] = useState(BILL_TIMING[0]);
  const [category, setCategory] = useState(SPENDING[0].name);
  const [threshold, setThreshold] = useState("80%");
  const [goal, setGoal] = useState(goals[0]?.name ?? "");
  const [milestone, setMilestone] = useState("50%");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [err, setErr] = useState("");

  const conf = ALERT_KINDS.find((k) => k.key === kind)!;

  function build(): { title: string; type: string } | null {
    if (kind === "Stock Price") {
      const p = Math.abs(Number(price.replace(/[^0-9.]/g, "")));
      if (!p) { setErr("Enter a target price"); return null; }
      return { title: `${symbol} ${direction} PKR ${p}`, type: "Stock Price Alert" };
    }
    if (kind === "Bill Reminder") {
      if (!bill) { setErr("Pick a bill"); return null; }
      return { title: `${bill} — ${timing}`, type: "Bill Reminder" };
    }
    if (kind === "Budget") return { title: `${category} ${threshold} of budget`, type: "Budget Alert" };
    if (!goal) { setErr("Pick a goal"); return null; }
    return { title: `${goal} ${milestone} reached`, type: "Goal Milestone" };
  }

  function submit() {
    setErr("");
    if (!push && !email) return setErr("Choose at least one channel");
    const built = build();
    if (!built) return;
    const channels = [push && "Push", email && "Email"].filter(Boolean).join(" · ");
    financeActions.addAlert({ emoji: conf.emoji, title: built.title, type: built.type, meta: channels, on: true }, `New alert: ${built.title}`);
    setPrice("");
    onClose();
    onToast("Alert created");
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
          <SelectRow label="Symbol"><ChipRow options={STOCK_LIST.map((s) => s.ticker)} value={symbol} onChange={setSymbol} /></SelectRow>
          <SelectRow label="Condition"><Segmented options={["Above", "Below"]} value={direction} onChange={setDirection} /></SelectRow>
          <Field label="Target price (PKR)" value={price} onChangeText={setPrice} placeholder="0" keyboardType="numeric" inputMode="numeric" />
        </>
      )}
      {kind === "Bill Reminder" && (
        <>
          <SelectRow label="Bill"><ChipRow options={bills.map((b) => b.name)} value={bill} onChange={setBill} /></SelectRow>
          <SelectRow label="Remind me"><ChipRow options={BILL_TIMING} value={timing} onChange={setTiming} /></SelectRow>
        </>
      )}
      {kind === "Budget" && (
        <>
          <SelectRow label="Category"><ChipRow options={SPENDING.map((s) => s.name)} value={category} onChange={setCategory} /></SelectRow>
          <SelectRow label="Threshold"><Segmented options={BUDGET_THRESHOLDS} value={threshold} onChange={setThreshold} /></SelectRow>
        </>
      )}
      {kind === "Goal Milestone" && (
        <>
          <SelectRow label="Goal"><ChipRow options={goals.map((g) => g.name)} value={goal} onChange={setGoal} /></SelectRow>
          <SelectRow label="Milestone"><Segmented options={GOAL_MILESTONES} value={milestone} onChange={setMilestone} /></SelectRow>
        </>
      )}

      <View style={styles.channels}>
        <Checkbox label="Push" checked={push} onToggle={() => setPush((v) => !v)} />
        <Checkbox label="Email" checked={email} onToggle={() => setEmail((v) => !v)} />
      </View>

      {err ? <Text style={styles.err}>{err}</Text> : null}
      <GlassPrimaryButton label="Create Alert" icon={<Plus color={colors.primaryForeground} size={16} />} onPress={submit} />
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
