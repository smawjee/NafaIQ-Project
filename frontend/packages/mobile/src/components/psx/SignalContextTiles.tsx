// Context tiles under the Technical Setup verdict. Mirrors web
// src/features/signals/SignalContextTiles.tsx: an external TradingView
// cross-check, the trend state (with suggested stop / volatility), and the
// market-wide FIPI foreign-flow read — each only when the backend sent it.
import { StyleSheet, View } from "react-native";

import { Text } from "@/components/ui";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import type { ApiSignalV2 } from "@nafaiq/shared";

const TREND_LABELS: Record<string, string> = {
  UPTREND: "Uptrend",
  WEAKENING: "Weakening",
  DOWNTREND: "Downtrend",
  BASING: "Basing",
  RANGE: "Range-bound",
  UNKNOWN: "Insufficient history",
};

const FLOW_LABELS: Record<string, string> = {
  FOREIGN_BUYING: "Foreigners buying",
  FOREIGN_SELLING: "Foreigners selling",
  MIXED: "Mixed flows",
  NEUTRAL: "Neutral",
};

/** Compact signed PKR for flow figures, e.g. +Rs 1.2B / -Rs 340M. */
function formatPkr(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "+";
  if (abs >= 1e9) return `${sign}Rs ${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}Rs ${(abs / 1e6).toFixed(0)}M`;
  return `${sign}Rs ${abs.toFixed(0)}`;
}

type Tone = "bull" | "bear" | "muted";

function Tile({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone: Tone }) {
  const { colors } = useTheme();
  const valueColor =
    tone === "bull" ? colors.bull : tone === "bear" ? colors.bear : colors.textPrimary;
  return (
    <View
      style={[styles.tile, { backgroundColor: colors.glassFill, borderColor: colors.border }]}
      accessibilityLabel={`${label}: ${value}${detail ? `. ${detail}` : ""}`}
    >
      <Text variant="muted" style={styles.label}>
        {label}
      </Text>
      <Text style={[styles.value, { color: valueColor }]}>{value}</Text>
      {detail ? (
        <Text variant="muted" style={styles.detail} numberOfLines={2}>
          {detail}
        </Text>
      ) : null}
    </View>
  );
}

export function SignalContextTiles({ signal }: { signal: ApiSignalV2 }) {
  const { t } = useLang();
  const consensus = signal.consensus ?? null;
  const trend = signal.trend_state ?? null;
  const risk = signal.risk_metrics ?? null;
  const flow = signal.flow_context ?? null;
  if (!consensus && !trend && !flow) return null;

  const agreement = signal.consensus_agreement ?? null;
  const agreementValue =
    agreement === "AGREES"
      ? t("Aligned")
      : agreement === "DISAGREES"
        ? t("Divergent")
        : agreement === "MIXED"
          ? t("Mixed")
          : t("Available");

  return (
    <View style={styles.row}>
      {consensus ? (
        <Tile
          label={t("External check")}
          value={agreementValue}
          detail={t("TradingView technicals")}
          tone={agreement === "AGREES" ? "bull" : agreement === "DISAGREES" ? "bear" : "muted"}
        />
      ) : null}
      {trend ? (
        <Tile
          label={t("Trend state")}
          value={t(TREND_LABELS[trend] ?? trend)}
          detail={
            risk
              ? `${t("Stop")} ${(risk.suggested_stop_pct * 100).toFixed(1)}% · ${t("Vol")} ${(risk.annualized_volatility * 100).toFixed(0)}%`
              : undefined
          }
          tone={
            trend === "UPTREND" || trend === "BASING"
              ? "bull"
              : trend === "DOWNTREND" || trend === "WEAKENING"
                ? "bear"
                : "muted"
          }
        />
      ) : null}
      {flow ? (
        <Tile
          label={t("Foreign flow (FIPI)")}
          value={t(FLOW_LABELS[flow.trend] ?? flow.trend)}
          detail={`5d ${formatPkr(flow.foreign_net_5d_pkr)} · 20d ${formatPkr(flow.foreign_net_20d_pkr)}`}
          tone={
            flow.trend === "FOREIGN_BUYING" ? "bull" : flow.trend === "FOREIGN_SELLING" ? "bear" : "muted"
          }
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  tile: {
    flexGrow: 1,
    flexBasis: "30%",
    minWidth: 104,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 10,
    padding: 10,
    gap: 3,
  },
  label: { fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, fontWeight: "600" },
  value: { fontSize: 13, fontWeight: "700" },
  detail: { fontSize: 10 },
});
