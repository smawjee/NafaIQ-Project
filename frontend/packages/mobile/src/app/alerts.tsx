// Alerts (`/alerts`). Mirrors web /alerts: active alerts with toggles + delete,
// add-alert form (4 types, conditional fields, push/email), notification history.
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, TextInput, View } from "react-native";

import { Screen } from "@/components/Screen";
import { Button, Card, Text } from "@/components/ui";
import { ChipRow } from "@/components/ui/controls";
import { radii, type ThemeColors } from "@/constants/theme";
import { financeActions, useFinanceStore } from "@/hooks/use-finance-store";
import { useTheme } from "@/hooks/use-theme";
import { type Alert } from "@nafaiq/shared";
import { Calendar, Check, iconFor, Target, Trash2, TrendingUp, Wallet } from "@/lib/icons";

const TYPES = [
  { label: "Stock Price", icon: TrendingUp, emoji: "🔔" },
  { label: "Bill Reminder", icon: Calendar, emoji: "📅" },
  { label: "Budget", icon: Wallet, emoji: "💸" },
  { label: "Goal Milestone", icon: Target, emoji: "🎯" },
];

export default function AlertsScreen() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { alerts, notifications } = useFinanceStore();
  const [type, setType] = useState("Stock Price");
  const [stock, setStock] = useState("HBL");
  const [dir, setDir] = useState("Above");
  const [price, setPrice] = useState("");
  const [bill, setBill] = useState("SNGPL Gas");
  const [timing, setTiming] = useState("3 days before");
  const [push, setPush] = useState(true);
  const [email, setEmail] = useState(false);
  const [error, setError] = useState("");

  function handleCreate() {
    setError("");
    const ty = TYPES.find((x) => x.label === type)!;
    let title = "";
    let meta = "";
    if (type === "Stock Price") {
      const num = Number(price);
      if (!price || Number.isNaN(num) || num <= 0) {
        setError("Please enter a valid price.");
        return;
      }
      title = `${stock} ${dir.toLowerCase()} PKR ${num}`;
      meta = "Created " + new Date().toLocaleString("en-US", { month: "short", day: "numeric" });
    } else if (type === "Bill Reminder") {
      title = `${bill} — ${timing}`;
      meta = "Recurring monthly";
    } else if (type === "Budget") {
      title = `${bill} budget alert`;
      meta = "Monthly";
    } else {
      title = "Goal milestone alert";
      meta = "One-time";
    }
    const channels = [push && "Push", email && "Email"].filter(Boolean).join(" + ") || "In-app";
    const alert: Alert = { emoji: ty.emoji, title, type: `${type} Alert`, meta, on: true };
    financeActions.addAlert(alert, `New alert created: ${title} (${channels})`);
    setPrice("");
  }

  return (
    <Screen title="Alerts">
      {/* Active alerts */}
      <Text variant="title">Active Alerts</Text>
      <View style={{ gap: 8 }}>
        {alerts.map((a, i) => {
          const Icon = iconFor(a.emoji);
          return (
            <Card key={a.title} style={styles.alertRow}>
              <View style={styles.iconBox}>
                <Icon color={colors.textSecondary} size={16} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "600" }}>{a.title}</Text>
                <Text variant="muted">{a.type} · {a.meta}</Text>
              </View>
              <Switch
                value={a.on}
                onValueChange={() => financeActions.toggleAlert(i)}
                trackColor={{ true: colors.bull, false: colors.elevated }}
                thumbColor="#fff"
                accessibilityLabel={`Toggle alert ${a.title}`}
              />
              <Pressable
                onPress={() => financeActions.removeAlert(i)}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={`Delete alert ${a.title}`}
              >
                <Trash2 color={colors.textMuted} size={16} />
              </Pressable>
            </Card>
          );
        })}
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
            <ChipRow options={["HBL", "ENGRO", "LUCK", "OGDC"]} value={stock} onChange={setStock} />
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
        ) : (
          <View style={{ gap: 10 }}>
            <ChipRow options={["SNGPL Gas", "PTCL Internet", "Apartment Rent"]} value={bill} onChange={setBill} />
            <ChipRow options={["1 day before", "3 days before", "7 days before"]} value={timing} onChange={setTiming} />
          </View>
        )}

        <View style={{ flexDirection: "row", gap: 20 }}>
          <Checkbox label="Push" value={push} onToggle={() => setPush((v) => !v)} />
          <Checkbox label="Email" value={email} onToggle={() => setEmail((v) => !v)} />
        </View>

        {error ? <Text style={{ color: colors.bear, fontSize: 12 }}>{error}</Text> : null}
        <Button title="Create Alert" onPress={handleCreate} />
      </Card>

      {/* Notification history */}
      <Text variant="title">Notification History</Text>
      <Card style={{ gap: 0, padding: 0 }}>
        {notifications.map((n, i) => {
          const Icon = iconFor(n.emoji);
          return (
            <View key={i} style={[styles.notif, i > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
              <View style={styles.iconBox}>
                <Icon color={colors.textSecondary} size={15} />
              </View>
              <View style={{ flex: 1 }}>
                <Text variant="body">{n.msg}</Text>
                <Text variant="muted">{n.time}</Text>
              </View>
              {!n.read && <View style={styles.unread} />}
            </View>
          );
        })}
      </Card>
    </Screen>
  );
}

function Checkbox({ label, value, onToggle }: { label: string; value: boolean; onToggle: () => void }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <Pressable onPress={onToggle} style={styles.checkbox} accessibilityRole="checkbox" accessibilityState={{ checked: value }}>
      <View style={[styles.box, value && { backgroundColor: colors.primary, borderColor: colors.primary }]}>
        {value && <Check color={colors.primaryForeground} size={12} />}
      </View>
      <Text variant="secondary">{label}</Text>
    </Pressable>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    alertRow: { flexDirection: "row", alignItems: "center", gap: 10 },
    iconBox: { width: 34, height: 34, borderRadius: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.elevated, alignItems: "center", justifyContent: "center" },
    typeGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    typeCard: { width: "47%", flexGrow: 1, alignItems: "center", gap: 6, borderWidth: 1, borderColor: c.border, borderRadius: 10, paddingVertical: 12 },
    input: { minHeight: 44, borderWidth: 1, borderColor: c.border, borderRadius: radii.btn, paddingHorizontal: 12, color: c.textPrimary, backgroundColor: c.elevated },
    checkbox: { flexDirection: "row", alignItems: "center", gap: 8 },
    box: { width: 20, height: 20, borderRadius: 4, borderWidth: 1, borderColor: c.borderHover, alignItems: "center", justifyContent: "center" },
    notif: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 12, paddingVertical: 12 },
    unread: { width: 8, height: 8, borderRadius: 4, backgroundColor: c.bull },
  });
