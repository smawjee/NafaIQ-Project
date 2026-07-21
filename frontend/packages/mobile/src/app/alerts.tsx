// Alerts (`/alerts`). Mirrors web /alerts backed by the live API:
// active alerts with toggles + delete (GET/PATCH/DELETE /api/alerts),
// add-alert form (4 types, conditional fields → POST /api/alerts),
// notification history (GET /api/alerts/events + PATCH .../read) with a
// "Check now" manual evaluate (POST /api/alerts/evaluate).
// History is a virtualized FlatList (psx.tsx pattern); sections live in its header.
import { useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert as RNAlert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Switch,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Card, Text } from "@/components/ui";
import { ChipRow } from "@/components/ui/controls";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import {
  type AlertEvent,
  type AlertEventType,
  useAlertEvents,
  useAllAlerts,
  useCreateAlert,
  useDeleteAlert,
  useEvaluateAlerts,
  useMarkAlertEventRead,
  useToggleAlert,
} from "@/hooks/queries/use-alerts";
import {
  type PriceAlert,
  useCreatePriceAlert,
  useDeletePriceAlert,
  usePriceAlerts,
} from "@/hooks/queries/use-price-alerts";
import { useAuth } from "@/hooks/use-auth";
import { useFinanceBills, useFinanceBudgets, useFinanceGoals } from "@/hooks/queries/use-finance";
import { useTheme } from "@/hooks/use-theme";
import {
  ArrowLeft,
  Bell,
  Calendar,
  Check,
  type LucideIcon,
  Target,
  TrendingUp,
  Trash2,
  Wallet,
} from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

const TYPES: { label: string; icon: LucideIcon; type: AlertEventType }[] = [
  { label: "Stock Price", icon: TrendingUp, type: "stock_price" },
  { label: "Bill Reminder", icon: Calendar, type: "bill" },
  { label: "Budget", icon: Wallet, type: "budget" },
  { label: "Goal Milestone", icon: Target, type: "goal" },
];

const TYPE_ICONS: Record<string, LucideIcon> = {
  stock_price: TrendingUp,
  bill: Calendar,
  budget: Wallet,
  goal: Target,
  system: Bell,
};

const TYPE_LABELS: Record<string, string> = {
  stock_price: "Stock Price",
  bill: "Bill Reminder",
  budget: "Budget",
  goal: "Goal Milestone",
  system: "System",
};

const STOCK_OPTIONS = ["HBL", "ENGRO", "LUCK", "OGDC"];
const TIMING_OPTIONS = ["1 day before", "3 days before", "7 days before"];
const THRESHOLD_OPTIONS = ["80%", "90%", "100%"];
const MILESTONE_OPTIONS = ["25%", "50%", "75%", "100%"];

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function AlertsScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { user } = useAuth();
  const signedIn = !!user;

  const alertsQuery = useAllAlerts(signedIn);
  const eventsQuery = useAlertEvents(50, signedIn);
  // Live bill/budget/goal picker options — same finance queries as web /alerts.
  const { data: billsData } = useFinanceBills(signedIn);
  const { data: budgetsData } = useFinanceBudgets(signedIn);
  const { data: goalsData } = useFinanceGoals(signedIn);
  const billOptions = useMemo(() => (billsData ?? []).map((b) => b.name), [billsData]);
  const budgetOptions = useMemo(() => (budgetsData ?? []).map((b) => b.category), [budgetsData]);
  const goalOptions = useMemo(() => (goalsData ?? []).map((g) => g.name), [goalsData]);
  const createAlert = useCreateAlert();
  const toggleAlert = useToggleAlert();
  const deleteAlert = useDeleteAlert();
  const markRead = useMarkAlertEventRead();
  const evaluate = useEvaluateAlerts();
  // Dedicated price alerts (price_alerts table) — carry persisted channels.
  const priceAlertsQuery = usePriceAlerts(signedIn);
  const createPriceAlert = useCreatePriceAlert();
  const deletePriceAlert = useDeletePriceAlert();

  const [type, setType] = useState("Stock Price");
  const [stock, setStock] = useState(STOCK_OPTIONS[0]);
  const [dir, setDir] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState("");
  const [timing, setTiming] = useState("3 days before");
  const [budgetCat, setBudgetCat] = useState("");
  const [threshold, setThreshold] = useState("80%");
  const [goal, setGoal] = useState("");
  const [milestone, setMilestone] = useState("50%");
  // Options load async — fall back to the first fetched row until a pick is made.
  const selectedBill = bill || billOptions[0] || "";
  const selectedBudgetCat = budgetCat || budgetOptions[0] || "";
  const selectedGoal = goal || goalOptions[0] || "";
  // Delivery channel prefs are client-side only for now: the app-alert API
  // (backend AppAlertCreate) has no channel field; events default to in_app.
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [error, setError] = useState("");

  function handleCreate() {
    setError("");
    // Build title + meta exactly like web features/alerts/Alerts.tsx handleCreate.
    let title = "";
    let meta: Record<string, unknown> = {};
    let alertType: AlertEventType = "stock_price";

    if (type === "Stock Price") {
      const num = Number(price);
      if (!price || Number.isNaN(num) || num <= 0) {
        setError("Please enter a valid price.");
        return;
      }
      // Stock price → dedicated price_alerts (persists notify_push/notify_email).
      createPriceAlert.mutate(
        {
          symbol: stock,
          condition: dir === "Above" ? "above" : "below",
          price: num,
          one_time: false,
          notify_push: push,
          notify_email: email,
        },
        {
          onSuccess: () => {
            setPrice("");
            setError("");
          },
          onError: (e) => setError(e instanceof Error ? e.message : "Failed to create alert."),
        },
      );
      return;
    } else if (type === "Bill Reminder") {
      if (!selectedBill) {
        setError("Please select a bill.");
        return;
      }
      title = `${selectedBill} — ${timing}`;
      meta = { bill: selectedBill, timing };
      alertType = "bill";
    } else if (type === "Budget") {
      if (!selectedBudgetCat) {
        setError("Please select a budget category.");
        return;
      }
      const pct = threshold.replace("%", "");
      title = `${selectedBudgetCat} at ${pct}% of budget`;
      meta = { category: selectedBudgetCat, threshold: pct };
      alertType = "budget";
    } else {
      if (!selectedGoal) {
        setError("Please select a goal.");
        return;
      }
      const pct = milestone.replace("%", "");
      title = `${selectedGoal} ${pct}% reached`;
      meta = { goal: selectedGoal, milestone: pct };
      alertType = "goal";
    }

    createAlert.mutate(
      { type: alertType, title, meta },
      {
        onSuccess: () => {
          setPrice("");
          setThreshold("80%");
          setMilestone("50%");
          setError("");
        },
        onError: (e) => {
          setError(e instanceof Error ? e.message : "Failed to create alert.");
        },
      },
    );
  }

  function confirmDelete(id: number, title: string) {
    RNAlert.alert("Delete Alert", `Delete "${title}"? This cannot be undone.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deleteAlert.mutate(id) },
    ]);
  }

  function confirmDeletePriceAlert(pa: PriceAlert) {
    const label = `${pa.symbol} ${pa.condition.replace("_", " ")} PKR ${pa.price}`;
    RNAlert.alert("Delete Price Alert", `Delete "${label}"?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deletePriceAlert.mutate(pa.id) },
    ]);
  }

  const priceAlerts = priceAlertsQuery.data ?? [];

  const events = eventsQuery.data ?? [];

  const renderEvent = useCallback(
    ({ item, index }: { item: AlertEvent; index: number }) => {
      const unread = !item.read_at;
      const first = index === 0;
      const last = index === events.length - 1;
      const when = formatWhen(item.created_at);
      return (
        <Pressable
          onPress={() => {
            if (unread) markRead.mutate(item.id);
          }}
          disabled={!unread}
          accessibilityRole="button"
          accessibilityLabel={`${unread ? "Unread notification" : "Notification"}: ${item.title || "alert"}. ${
            unread ? "Tap to mark as read." : ""
          }`}
          style={[
            styles.notif,
            first && styles.notifFirst,
            last && styles.notifLast,
            !first && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
          ]}
        >
          <View
            style={[
              styles.dot,
              { backgroundColor: item.alert_type === "stock_price" ? colors.bull : colors.warning },
            ]}
            accessibilityElementsHidden
          />
          <View style={{ flex: 1 }}>
            <Text variant="body">{item.title || "Alert"}</Text>
            {item.body ? <Text variant="muted">{item.body}</Text> : null}
            {when ? <Text variant="muted">{when}</Text> : null}
          </View>
          {unread && <View style={styles.unread} />}
        </Pressable>
      );
    },
    [styles, colors, events.length, markRead],
  );

  const alerts = alertsQuery.data ?? [];

  const header = (
    <View style={{ gap: 16, marginBottom: 8 }}>
      <View style={styles.titleRow}>
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel="Go back"
        >
          <ArrowLeft color={colors.textPrimary} size={22} />
        </Pressable>
        <Text variant="display" style={{ fontFamily: AVENIR }}>
          Alerts
        </Text>
      </View>

      {/* Active alerts */}
      <Text variant="title">Active Alerts</Text>
      <View style={{ gap: 8 }}>
        {alertsQuery.isPending && signedIn ? (
          <Card style={styles.centerCard}>
            <ActivityIndicator color={colors.primary} />
          </Card>
        ) : alertsQuery.isError ? (
          <Card style={styles.centerCard}>
            <Text variant="secondary">Could not load alerts.</Text>
            <Button title="Retry" variant="outline" onPress={() => alertsQuery.refetch()} />
          </Card>
        ) : alerts.length === 0 ? (
          <Card style={styles.centerCard}>
            <Text variant="secondary">No alerts yet. Create your first alert below.</Text>
          </Card>
        ) : (
          alerts.map((a) => {
            const Icon = TYPE_ICONS[a.type] ?? Bell;
            const label = TYPE_LABELS[a.type] ?? a.type;
            return (
              <Card key={a.id} style={styles.alertRow}>
                <View style={styles.iconBox}>
                  <Icon color={colors.textSecondary} size={16} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "600" }}>{a.title || "Untitled alert"}</Text>
                  <Text variant="muted">
                    {label} alert{a.triggered_at ? " · Triggered" : ""}
                  </Text>
                </View>
                <Switch
                  value={!!a.enabled}
                  onValueChange={(v) => toggleAlert.mutate({ id: a.id, enabled: v })}
                  disabled={toggleAlert.isPending}
                  trackColor={{ true: colors.bull, false: colors.elevated }}
                  thumbColor="#fff"
                  accessibilityLabel={`Toggle alert ${a.title}`}
                />
                <Pressable
                  onPress={() => confirmDelete(a.id, a.title)}
                  hitSlop={14}
                  disabled={deleteAlert.isPending}
                  accessibilityRole="button"
                  accessibilityLabel={`Delete alert ${a.title}`}
                >
                  <Trash2 color={colors.textMuted} size={16} />
                </Pressable>
              </Card>
            );
          })
        )}
      </View>

      {/* Price alerts (dedicated) */}
      <Text variant="title">Price Alerts</Text>
      <View style={{ gap: 8 }}>
        {priceAlertsQuery.isPending && signedIn ? (
          <Card style={styles.centerCard}>
            <ActivityIndicator color={colors.primary} />
          </Card>
        ) : priceAlerts.length === 0 ? (
          <Card style={styles.centerCard}>
            <Text variant="secondary">No price alerts. Add one with the Stock Price type below.</Text>
          </Card>
        ) : (
          priceAlerts.map((pa) => (
            <Card key={pa.id} style={styles.alertRow}>
              <View style={styles.iconBox}>
                <TrendingUp color={colors.textSecondary} size={16} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "600" }}>
                  {pa.symbol} {pa.condition.replace("_", " ")} PKR {pa.price}
                </Text>
                <Text variant="muted">
                  {pa.one_time ? "One-time" : "Repeating"}
                  {pa.enabled ? "" : " · Paused"}
                </Text>
              </View>
              <Pressable
                onPress={() => confirmDeletePriceAlert(pa)}
                hitSlop={14}
                disabled={deletePriceAlert.isPending}
                accessibilityRole="button"
                accessibilityLabel={`Delete price alert ${pa.symbol}`}
              >
                <Trash2 color={colors.textMuted} size={16} />
              </Pressable>
            </Card>
          ))
        )}
      </View>

      {/* Add new alert */}
      <Text variant="title">Add New Alert</Text>
      <Card style={{ gap: 14 }}>
        <View style={styles.typeGrid}>
          {TYPES.map((t) => {
            const active = type === t.label;
            const Icon = t.icon;
            return (
              <Pressable
                key={t.label}
                onPress={() => setType(t.label)}
                accessibilityRole="button"
                accessibilityLabel={`Alert type ${t.label}`}
                accessibilityState={{ selected: active }}
                style={[styles.typeCard, active && { borderColor: colors.primary, backgroundColor: colors.primary + "1a" }]}
              >
                <Icon color={active ? colors.primary : colors.textSecondary} size={20} />
                <Text style={{ fontSize: 12, color: active ? colors.primary : colors.textSecondary }}>{t.label}</Text>
              </Pressable>
            );
          })}
        </View>

        {type === "Stock Price" ? (
          <View style={{ gap: 10 }}>
            <ChipRow options={STOCK_OPTIONS} value={stock} onChange={setStock} />
            <ChipRow options={["Above", "Below"]} value={dir} onChange={setDir} />
            <TextInput
              value={price}
              onChangeText={setPrice}
              placeholder="Price (PKR)"
              placeholderTextColor={colors.textMuted}
              keyboardType="numeric"
              style={styles.input}
              accessibilityLabel="Target price"
            />
          </View>
        ) : type === "Bill Reminder" ? (
          <View style={{ gap: 10 }}>
            {billOptions.length === 0 ? (
              <Text variant="muted">No bills yet. Add bills from Finance first.</Text>
            ) : (
              <ChipRow options={billOptions} value={selectedBill} onChange={setBill} />
            )}
            <ChipRow options={TIMING_OPTIONS} value={timing} onChange={setTiming} />
          </View>
        ) : type === "Budget" ? (
          <View style={{ gap: 10 }}>
            {budgetOptions.length === 0 ? (
              <Text variant="muted">No budgets yet. Add budgets from Finance first.</Text>
            ) : (
              <ChipRow options={budgetOptions} value={selectedBudgetCat} onChange={setBudgetCat} />
            )}
            <ChipRow options={THRESHOLD_OPTIONS} value={threshold} onChange={setThreshold} />
          </View>
        ) : (
          <View style={{ gap: 10 }}>
            {goalOptions.length === 0 ? (
              <Text variant="muted">No goals yet. Add goals from Finance first.</Text>
            ) : (
              <ChipRow options={goalOptions} value={selectedGoal} onChange={setGoal} />
            )}
            <ChipRow options={MILESTONE_OPTIONS} value={milestone} onChange={setMilestone} />
          </View>
        )}

        {/* Channels are persisted only for price alerts (backend supports
            notify_push/notify_email there); bill/budget/goal have no channel. */}
        {type === "Stock Price" ? (
          <View style={{ flexDirection: "row", gap: 20 }}>
            <Checkbox label="Push" value={push} onToggle={() => setPush((v) => !v)} />
            <Checkbox label="Email" value={email} onToggle={() => setEmail((v) => !v)} />
          </View>
        ) : null}

        {error ? <Text style={{ color: colors.bear, fontSize: 12 }}>{error}</Text> : null}
        <Button
          title="Create Alert"
          onPress={handleCreate}
          loading={createAlert.isPending || createPriceAlert.isPending}
        />
      </Card>

      {/* Notification history header */}
      <View style={styles.between}>
        <Text variant="title">Notification History</Text>
        <Pressable
          onPress={() => evaluate.mutate()}
          disabled={evaluate.isPending || !signedIn}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Check alerts now"
          accessibilityState={{ disabled: evaluate.isPending || !signedIn, busy: evaluate.isPending }}
          style={[styles.checkBtn, (evaluate.isPending || !signedIn) && { opacity: 0.5 }]}
        >
          <Text style={{ fontSize: 12, fontWeight: "600", color: colors.textSecondary }}>
            {evaluate.isPending ? "Checking..." : "Check now"}
          </Text>
        </Pressable>
      </View>
      {eventsQuery.isPending && signedIn ? (
        <Card style={styles.centerCard}>
          <ActivityIndicator color={colors.primary} />
        </Card>
      ) : null}
    </View>
  );

  return (
    <GlassScreen>
      <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <FlatList
            data={eventsQuery.isPending ? [] : events}
            keyExtractor={(ev) => String(ev.id)}
            renderItem={renderEvent}
            ListHeaderComponent={header}
            ListEmptyComponent={
              eventsQuery.isPending && signedIn ? null : eventsQuery.isError ? (
                <Card style={styles.centerCard}>
                  <Text variant="secondary">Could not load notifications.</Text>
                  <Button title="Retry" variant="outline" onPress={() => eventsQuery.refetch()} />
                </Card>
              ) : (
                <Card style={styles.centerCard}>
                  <Text variant="secondary">No notifications yet.</Text>
                  <Text variant="muted" style={{ textAlign: "center" }}>
                    Your triggered alerts will appear here. Tap &quot;Check now&quot; to evaluate alerts manually.
                  </Text>
                </Card>
              )
            }
            contentContainerStyle={{ padding: 16, paddingBottom: 28 }}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          />
        </KeyboardAvoidingView>
      </SafeAreaView>
    </GlassScreen>
  );
}

function Checkbox({ label, value, onToggle }: { label: string; value: boolean; onToggle: () => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <Pressable
      onPress={onToggle}
      hitSlop={12}
      style={styles.checkbox}
      accessibilityRole="checkbox"
      accessibilityLabel={`${label} notifications`}
      accessibilityState={{ checked: value }}
    >
      <View style={[styles.box, value && { backgroundColor: colors.primary, borderColor: colors.primary }]}>
        {value && <Check color={colors.primaryForeground} size={12} />}
      </View>
      <Text variant="secondary">{label}</Text>
    </Pressable>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    titleRow: { flexDirection: "row", alignItems: "center", gap: 6 },
    backBtn: { minWidth: 40, minHeight: 40, alignItems: "center", justifyContent: "center", marginLeft: -10 },
    alertRow: { flexDirection: "row", alignItems: "center", gap: 10 },
    iconBox: { width: 34, height: 34, borderRadius: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, alignItems: "center", justifyContent: "center" },
    typeGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    typeCard: { width: "47%", flexGrow: 1, alignItems: "center", gap: 6, borderWidth: 1, borderColor: c.border, borderRadius: 10, paddingVertical: 12 },
    input: { minHeight: 44, borderWidth: 1, borderColor: c.border, borderRadius: radii.btn, paddingHorizontal: 12, color: c.textPrimary, backgroundColor: c.glassFill },
    checkbox: { flexDirection: "row", alignItems: "center", gap: 8, minHeight: 32 },
    box: { width: 20, height: 20, borderRadius: 4, borderWidth: 1, borderColor: c.borderHover, alignItems: "center", justifyContent: "center" },
    checkBtn: { minHeight: 32, justifyContent: "center", paddingHorizontal: 10, borderWidth: 1, borderColor: c.border, borderRadius: radii.btn },
    centerCard: { alignItems: "center", gap: 10, paddingVertical: 20 },
    notif: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 12, paddingVertical: 12, minHeight: 44, backgroundColor: c.glassFill, borderLeftWidth: 1, borderRightWidth: 1, borderColor: c.border },
    notifFirst: { borderTopWidth: 1, borderTopLeftRadius: radii.card, borderTopRightRadius: radii.card },
    notifLast: { borderBottomWidth: 1, borderBottomLeftRadius: radii.card, borderBottomRightRadius: radii.card },
    dot: { width: 8, height: 8, borderRadius: 4 },
    unread: { width: 8, height: 8, borderRadius: 4, backgroundColor: c.bull },
  });
