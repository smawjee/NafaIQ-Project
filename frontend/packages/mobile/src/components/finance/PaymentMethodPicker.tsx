// Payment-method chips for the add/edit-transaction sheet. Mirrors web
// QuickAddTransactionModal's payment-method select + "Add new payment method"
// flow: the options come from /finance/vocabulary (per-user, seeded defaults +
// anything the user saved), and a "+ New" chip reveals an inline field that
// persists via POST /finance/payment-methods.
import { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { Field } from "@/components/Modal";
import { Button, Text } from "@/components/ui";
import { Chip } from "@/components/ui/controls";
import { useLang } from "@/hooks/use-lang";

export function PaymentMethodPicker({
  options,
  value,
  onChange,
  onCreate,
  creating,
  formatLabel,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  /** Persist + select a brand-new method; the parent owns the mutation. */
  onCreate: (label: string) => void;
  creating?: boolean;
  /**
   * Display-only relabelling; the option's stored value is what gets selected.
   * Backend-generated sources ("stock_trade") share this field with real
   * payment methods and must round-trip untouched — the finance summaries key
   * off `source = 'stock_trade'` to keep share purchases out of expense
   * totals — so only the chip text changes.
   */
  formatLabel?: (value: string) => string;
}) {
  const { t } = useLang();
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("");

  const save = () => {
    const clean = label.trim();
    if (!clean) return;
    const existing = options.find((o) => o.toLowerCase() === clean.toLowerCase());
    if (existing) onChange(existing);
    else onCreate(clean);
    setLabel("");
    setAdding(false);
  };

  return (
    <View style={{ gap: 8 }}>
      <Text variant="secondary">{t("Payment method")}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
        {options.map((o) => (
          <Chip
            key={o}
            label={formatLabel ? formatLabel(o) : o}
            active={!adding && o === value}
            onPress={() => {
              setAdding(false);
              onChange(o);
            }}
          />
        ))}
        <Chip label={`+ ${t("New")}`} active={adding} onPress={() => setAdding(true)} />
      </ScrollView>
      {adding ? (
        <View style={styles.addRow}>
          <View style={{ flex: 1 }}>
            <Field
              label=""
              value={label}
              onChangeText={setLabel}
              placeholder={t("e.g. Allied Bank Card, Cheque")}
              autoFocus
            />
          </View>
          <Button title={t("Save")} variant="outline" onPress={save} loading={creating} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingVertical: 2 },
  addRow: { flexDirection: "row", alignItems: "flex-end", gap: 8 },
});
