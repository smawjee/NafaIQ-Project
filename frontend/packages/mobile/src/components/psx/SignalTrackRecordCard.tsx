// Live, audited signal track record. Mirrors web
// src/features/signals/SignalTrackRecordCard.tsx: matured outcomes only,
// measured against real prices after publication — never edited. Renders
// nothing while loading or when the endpoint is unavailable, exactly like web.
import { StyleSheet, View } from "react-native";

import { Card, Text } from "@/components/ui";
import { usePsxSignalTrackRecord } from "@/hooks/queries/use-market";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import type { ApiTrackRecordEntry } from "@nafaiq/shared";

const SIGNAL_ORDER = ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"] as const;

function pct(value: number | undefined | null): string {
  if (value === undefined || value === null) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function Row({ label, hint, entry, isSell }: {
  label: string;
  hint: string | null;
  entry: ApiTrackRecordEntry;
  isSell: boolean;
}) {
  const { colors } = useTheme();
  // For sell calls the honest headline is "did the fall happen" — the
  // avoided-loss rate — not a long-side hit rate.
  const headline = isSell ? (entry.avoided_loss_rate ?? entry.hit_rate) : entry.hit_rate;
  return (
    <View style={[styles.row, { borderColor: colors.border }]}>
      <View style={styles.signalCell}>
        <Text variant="body" style={{ fontWeight: "600", fontSize: 13 }}>
          {label}
        </Text>
        {hint ? (
          <Text variant="muted" style={{ fontSize: 10 }}>
            {hint}
          </Text>
        ) : null}
      </View>
      <Text variant="mono" style={[styles.numCell, { color: colors.textSecondary }]}>
        {entry.n}
      </Text>
      <Text
        variant="mono"
        style={[styles.numCell, { color: headline >= 0.5 ? colors.bull : colors.bear }]}
      >
        {pct(headline)}
      </Text>
      <Text
        variant="mono"
        style={[styles.numCell, { color: entry.avg_excess >= 0 ? colors.bull : colors.bear }]}
      >
        {(entry.avg_excess * 100).toFixed(1)}%
      </Text>
    </View>
  );
}

export function SignalTrackRecordCard() {
  const { colors } = useTheme();
  const { t } = useLang();
  const { data, isLoading } = usePsxSignalTrackRecord();

  if (isLoading || !data) return null;

  const entries = SIGNAL_ORDER.filter((s) => data.by_signal[s]);

  return (
    <Card style={{ gap: 10 }}>
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text variant="title">{t("Signal Track Record")}</Text>
          <Text variant="muted">
            {t("Measured against real prices after publication — never edited")}
          </Text>
        </View>
        <View style={[styles.chip, { backgroundColor: colors.glassFill, borderColor: colors.border }]}>
          <Text variant="muted" style={{ fontSize: 10, fontWeight: "600" }}>
            {data.matured_total} {t("matured")} · {data.pending_maturity} {t("pending")}
          </Text>
        </View>
      </View>

      {data.matured_total === 0 ? (
        <View style={[styles.empty, { backgroundColor: colors.glassFill, borderColor: colors.border }]}>
          <Text variant="muted">
            {t(
              "Signals are being recorded daily. The first outcomes appear once published signals reach their horizon — results shown here will be the audited history, not a claim.",
            )}
          </Text>
        </View>
      ) : (
        <View>
          <View style={[styles.head, { borderColor: colors.border }]}>
            <Text variant="muted" style={[styles.signalCell, styles.headText]}>
              {t("Signal")}
            </Text>
            <Text variant="muted" style={[styles.numCell, styles.headText]}>
              {t("Count")}
            </Text>
            <Text variant="muted" style={[styles.numCell, styles.headText]}>
              {t("Hit rate")}
            </Text>
            <Text variant="muted" style={[styles.numCell, styles.headText]}>
              {t("vs KSE-100")}
            </Text>
          </View>
          {entries.map((sig) => {
            const isSell = sig === "SELL" || sig === "STRONG_SELL";
            return (
              <Row
                key={sig}
                label={t(sig.replace("_", " "))}
                hint={isSell ? t("(fall avoided)") : null}
                entry={data.by_signal[sig]}
                isSell={isSell}
              />
            );
          })}
        </View>
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  chip: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  empty: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 10, padding: 12 },
  head: { flexDirection: "row", borderBottomWidth: 1, paddingBottom: 6, marginBottom: 2 },
  headText: { fontSize: 10, textTransform: "uppercase", letterSpacing: 0.4 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 40,
    paddingVertical: 6,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  signalCell: { flex: 1.4, gap: 1 },
  numCell: { flex: 1, textAlign: "right", fontSize: 13 },
});
