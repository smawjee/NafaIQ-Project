import { PRICE_CONDITIONS } from "@nafaiq/shared";
// The confirmation step for a write the assistant proposed. Port of web
// features/assistant/components/ActionDraftCard.tsx to the glass RN idiom.
//
// Every field is editable, including ones the model inferred — a misheard
// "fifty" vs "fifteen" has to be one tap to fix, not a reason to start over.
// Fields the agent is still missing are highlighted and focused first.
//
// Field definitions are driven by the draft's `action`, mirroring the parameter
// models in backend/src/app/services/assistant/tools.py. The server re-validates
// everything regardless, so this file's job is clarity, not enforcement.

import { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from "react-native";

import { Field } from "@/components/Modal";
import { GlassCard } from "@/components/glass/GlassCard";
import { Text } from "@/components/ui";
import { Chip } from "@/components/ui/controls";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { Check, X } from "@/lib/icons";
import type { ActionDraft } from "@/lib/assistant/client";

type FieldKind = "text" | "number" | "date" | "select";

interface FieldDef {
  name: string;
  label: string;
  kind: FieldKind;
  options?: readonly string[];
}

const TXN_TYPES = ["expense", "income"] as const;
const TRADE_SIDES = ["buy", "sell"] as const;

// Mirrors web finance.data.ts (the full lists, not the 4-account mobile
// quick-add subset) so the agent's inferred values always have a chip.
const CATEGORIES = [
  "Food & Dining",
  "Groceries",
  "Transport",
  "Utilities",
  "Shopping",
  "Subscriptions",
  "Savings",
  "Income",
] as const;
const ACCOUNTS = [
  "HBL Current",
  "Meezan Debit",
  "Easypaisa",
  "Meezan Savings",
  "Allied Bank Card",
  "Cheque",
  "Cash",
  "Bank Transfer",
] as const;

/** Per-action field layout. Keys match the tool parameter models. */
const FIELDS: Record<string, FieldDef[]> = {
  add_transaction: [
    { name: "merchant", label: "Merchant", kind: "text" },
    { name: "amount", label: "Amount (PKR)", kind: "number" },
    { name: "transaction_type", label: "Type", kind: "select", options: TXN_TYPES },
    { name: "category", label: "Category", kind: "select", options: CATEGORIES },
    { name: "source", label: "Paid via", kind: "select", options: ACCOUNTS },
    { name: "note", label: "Note", kind: "text" },
  ],
  add_bill: [
    { name: "name", label: "Bill", kind: "text" },
    { name: "amount", label: "Amount (PKR)", kind: "number" },
    { name: "due_date", label: "Due date", kind: "date" },
  ],
  add_goal: [
    { name: "name", label: "Goal", kind: "text" },
    { name: "target", label: "Target (PKR)", kind: "number" },
    { name: "saved", label: "Already saved (PKR)", kind: "number" },
    { name: "target_date", label: "Target date", kind: "date" },
  ],
  contribute_to_goal: [
    { name: "goal_name", label: "Goal", kind: "text" },
    { name: "amount", label: "Amount (PKR)", kind: "number" },
  ],
  add_holding: [
    { name: "symbol", label: "Symbol", kind: "text" },
    { name: "shares", label: "Shares", kind: "number" },
    { name: "avg_cost", label: "Average cost (PKR)", kind: "number" },
  ],
  record_trade: [
    { name: "symbol", label: "Symbol", kind: "text" },
    { name: "side", label: "Side", kind: "select", options: TRADE_SIDES },
    { name: "quantity", label: "Quantity", kind: "number" },
    { name: "price", label: "Price (PKR)", kind: "number" },
    { name: "fees", label: "Fees (PKR)", kind: "number" },
  ],
  add_goal_alert: [
    { name: "goal_name", label: "Goal", kind: "text" },
    { name: "milestone", label: "Alert at (%)", kind: "number" },
  ],
  add_price_alert: [
    { name: "symbol", label: "Symbol", kind: "text" },
    // Every condition the backend accepts, from the shared list — this offered
    // only above/below, so the assistant could draft a volume or 52-week alert
    // that the user then could not confirm without changing it.
    {
      name: "condition",
      label: "Alert when",
      kind: "select",
      options: PRICE_CONDITIONS.map((c) => c.value),
    },
    { name: "price", label: "Threshold", kind: "number" },
  ],
  add_to_watchlist: [{ name: "symbol", label: "Symbol", kind: "text" }],
  remove_from_watchlist: [{ name: "symbol", label: "Symbol", kind: "text" }],
};

const TITLES: Record<string, string> = {
  add_transaction: "Add transaction",
  add_bill: "Add bill",
  add_goal: "Create savings goal",
  contribute_to_goal: "Add to goal",
  add_holding: "Add holding",
  record_trade: "Record trade",
  add_goal_alert: "Add goal alert",
  add_price_alert: "Add price alert",
  add_to_watchlist: "Add to watchlist",
  remove_from_watchlist: "Remove from watchlist",
};

/** Chip options widened to include whatever the draft actually holds.
 * `source` is free text server-side ("via cash" -> "Cash"); a value outside
 * the picker must stay selectable, not silently disappear. */
function optionsFor(field: FieldDef, current: string | undefined): string[] {
  const options = [...(field.options ?? [])];
  const value = current?.trim();
  if (value && !options.includes(value)) options.unshift(value);
  return options;
}

interface Props {
  draft: ActionDraft;
  busy: boolean;
  onConfirm(args: Record<string, unknown>): void;
  onCancel(): void;
}

export function ActionDraftCard({ draft, busy, onConfirm, onCancel }: Props) {
  const { t } = useLang();
  const { colors } = useTheme();
  const fields = FIELDS[draft.action] ?? [];

  // Seeded from the draft, then owned by the user. Kept as strings so a
  // half-typed "12." doesn't get coerced to NaN mid-keystroke.
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      fields.map((f) => [f.name, draft.args[f.name] == null ? "" : String(draft.args[f.name])]),
    ),
  );

  const missing = useMemo(() => new Set(draft.missing), [draft.missing]);

  const stillMissing = fields
    .filter((f) => missing.has(f.name) && !values[f.name]?.trim())
    .map((f) => f.label);

  const submit = () => {
    if (busy || stillMissing.length > 0) return;
    const args: Record<string, unknown> = {};
    for (const f of fields) {
      const raw = values[f.name]?.trim();
      if (!raw) continue;
      args[f.name] = f.kind === "number" ? Number(raw) : raw;
    }
    // Fields the model set that this card doesn't render (portfolio_id,
    // transaction_date) must survive the round trip, or the server would have
    // to re-infer them.
    for (const [key, value] of Object.entries(draft.args)) {
      if (!(key in args) && value != null && !fields.some((f) => f.name === key)) {
        args[key] = value;
      }
    }
    onConfirm(args);
  };

  return (
    <GlassCard radius={12} style={[styles.card, { borderColor: colors.bull + "66" }]}>
      <Text style={[styles.title, { color: colors.bull }]}>
        {t(TITLES[draft.action] ?? draft.action)}
      </Text>

      <View style={{ gap: 8 }}>
        {fields.map((f) => {
          const isMissing = missing.has(f.name) && !values[f.name]?.trim();
          if (f.kind === "select") {
            return (
              <View key={f.name} style={{ gap: 4 }}>
                <Text variant="secondary" style={isMissing ? { color: colors.warning } : undefined}>
                  {t(f.label)}
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
                  {optionsFor(f, values[f.name]).map((o) => (
                    <Chip
                      key={o}
                      label={t(o)}
                      active={values[f.name] === o}
                      onPress={() => setValues((v) => ({ ...v, [f.name]: o }))}
                    />
                  ))}
                </ScrollView>
              </View>
            );
          }
          return (
            <View key={f.name} style={isMissing ? [styles.missing, { borderColor: colors.warning }] : undefined}>
              <Field
                label={isMissing ? `${t(f.label)} *` : t(f.label)}
                value={values[f.name] ?? ""}
                onChangeText={(text) => setValues((v) => ({ ...v, [f.name]: text }))}
                keyboardType={f.kind === "number" ? "decimal-pad" : "default"}
                placeholder={f.kind === "date" ? "YYYY-MM-DD" : undefined}
                // The first gap gets focus: it is what the agent just asked about.
                autoFocus={isMissing && f.name === draft.missing[0]}
              />
            </View>
          );
        })}
      </View>

      {stillMissing.length > 0 && (
        <Text style={{ color: colors.warning, fontSize: 11 }}>
          {t("Still needed")}: {stillMissing.map((l) => t(l)).join(", ")}
        </Text>
      )}

      <View style={styles.actions}>
        <Pressable
          onPress={submit}
          disabled={busy || stillMissing.length > 0}
          accessibilityRole="button"
          accessibilityLabel={t("Confirm")}
          style={[
            styles.confirm,
            { backgroundColor: colors.bull },
            (busy || stillMissing.length > 0) && { opacity: 0.5 },
          ]}
        >
          {busy ? (
            <ActivityIndicator color={colors.bullForeground} size="small" />
          ) : (
            <Check color={colors.bullForeground} size={15} />
          )}
          <Text style={{ color: colors.bullForeground, fontWeight: "700", fontSize: 13 }}>
            {t("Confirm")}
          </Text>
        </Pressable>
        <Pressable
          onPress={onCancel}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel={t("Cancel")}
          style={[styles.cancel, { borderColor: colors.border }, busy && { opacity: 0.5 }]}
        >
          <X color={colors.textSecondary} size={15} />
          <Text variant="secondary" style={{ fontSize: 13 }}>
            {t("Cancel")}
          </Text>
        </Pressable>
      </View>
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  card: { padding: 12, gap: 10, borderWidth: 1 },
  title: { fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.6 },
  chips: { gap: 8, paddingVertical: 2 },
  missing: { borderWidth: 1, borderRadius: 10, padding: 4, margin: -4 },
  actions: { flexDirection: "row", gap: 8, marginTop: 2 },
  confirm: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    minHeight: 44,
    borderRadius: 8,
  },
  cancel: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    minHeight: 44,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
  },
});
