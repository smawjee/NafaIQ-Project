import { memo, useMemo } from "react";
import { StyleSheet, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import type { ApiSignalV4 } from "@/lib/signals-v4";

const RATING_TONE: Record<string, "bull" | "bear" | "muted"> = {
  "Strong Bullish": "bull",
  Bullish: "bull",
  Neutral: "muted",
  Bearish: "bear",
  "Strong Bearish": "bear",
};

const TREND: Record<string, string> = { UPTREND: "Uptrend", DOWNTREND: "Downtrend", BASING: "Basing", WEAKENING: "Weakening", RANGE: "Range-bound", UNKNOWN: "Unclear" };
const FLOW: Record<string, string> = { FOREIGN_BUYING: "Foreign buying", FOREIGN_SELLING: "Foreign selling", MIXED: "Mixed", NEUTRAL: "Flat" };

function billions(value?: number) {
  if (value == null) return "—";
  const n = value / 1_000_000_000;
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}B`;
}

export const SignalV4Panel = memo(function SignalV4Panel({ signal, loading }: { signal?: ApiSignalV4 | null; loading?: boolean }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const setup = signal?.technical_setup;
  const context = signal?.context;
  const ratingColor = RATING_TONE[setup?.rating ?? "Neutral"] === "bull" ? colors.bull : RATING_TONE[setup?.rating ?? "Neutral"] === "bear" ? colors.bear : colors.textMuted;

  return (
    <GlassCard style={{ gap: 13 }}>
      <View style={styles.between}>
        <View><Text variant="title">Technical Setup</Text><Text variant="muted">Confirmed EOD indicators only</Text></View>
        <Text style={{ color: ratingColor, fontFamily: fonts.headingMedium, fontWeight: "700" }}>{loading ? "Loading…" : setup?.rating ?? "Unavailable"}</Text>
      </View>

      {setup?.status === "available" ? (
        <>
          <View style={styles.chips}>
            {context?.relative_rank?.composite_percentile != null ? <Pill value={`Top ${Math.round(100 - context.relative_rank.composite_percentile)}% of PSX`} color={colors.primary} /> : null}
            {signal?.quality ? <Pill value={`${signal.quality.label} quality`} color={signal.quality.label === "High" ? colors.bull : signal.quality.label === "Low" ? colors.bear : colors.textSecondary} /> : null}
          </View>
          <View style={styles.voteGrid}>
            <Vote label="Bullish" value={setup.bullish_count} color={colors.bull} styles={styles} />
            <Vote label="Neutral" value={setup.neutral_count} color={colors.textMuted} styles={styles} />
            <Vote label="Bearish" value={setup.bearish_count} color={colors.bear} styles={styles} />
          </View>
          <View>
            {setup.components.slice(0, 8).map((item) => (
              <View key={item.name} style={styles.componentRow}>
                <View style={{ flex: 1 }}><Text variant="secondary" style={{ fontSize: 12 }}>{item.name}</Text><Text variant="muted" numberOfLines={1}>{item.reason}</Text></View>
                <Text style={{ color: item.vote > 0 ? colors.bull : item.vote < 0 ? colors.bear : colors.textMuted, fontSize: 12, fontWeight: "700" }}>{item.vote > 0 ? "Bullish" : item.vote < 0 ? "Bearish" : "Neutral"}</Text>
              </View>
            ))}
          </View>
        </>
      ) : <Text variant="secondary">{setup?.reason_code === "INSUFFICIENT_HISTORY" ? "Not enough verified history for a reliable setup." : "Verified market data is not available yet."}</Text>}

      {context ? (
        <View style={styles.contextGrid}>
          <Context label="Trend" value={TREND[context.trend_state ?? ""] ?? context.trend_state ?? "—"} styles={styles} />
          <Context label="Regime" value={context.regime ?? "—"} styles={styles} />
          <Context label="Risk" value={context.risk_level ?? context.risk_metrics?.position_risk ?? "—"} styles={styles} />
          <Context label="Foreign flow" value={FLOW[context.flow?.trend ?? ""] ?? context.flow?.trend ?? "—"} sub={`5d ${billions(context.flow?.foreign_net_5d_pkr)} · 20d ${billions(context.flow?.foreign_net_20d_pkr)}`} styles={styles} />
        </View>
      ) : null}

      {context?.risk_metrics ? <View style={styles.risk}><Text variant="muted">Risk metrics</Text><Text variant="mono" style={{ fontSize: 11 }}>{context.risk_metrics.suggested_stop_pct != null ? `Stop ${(context.risk_metrics.suggested_stop_pct * 100).toFixed(1)}%` : "No stop estimate"}{context.risk_metrics.expected_20d_move_pct != null ? ` · ±${(context.risk_metrics.expected_20d_move_pct * 100).toFixed(1)}% expected 20d move` : ""}</Text></View> : null}

      <View style={styles.forecast}><Text variant="muted">20-day event outlook</Text><Text style={{ fontSize: 12, fontWeight: "700" }}>{signal?.forecast.status === "published" ? signal.forecast.direction : signal?.forecast.headline ?? "No validated forecast yet"}</Text></View>
      <Text variant="muted" style={{ fontStyle: "italic", lineHeight: 17 }}>{signal?.disclosure ?? "Technical analysis and market context — not a forecast."}</Text>
    </GlassCard>
  );
});

function Pill({ value, color }: { value: string; color: string }) { return <View style={{ borderWidth: 1, borderColor: color + "55", backgroundColor: color + "12", borderRadius: 999, paddingHorizontal: 8, paddingVertical: 4 }}><Text style={{ color, fontSize: 10, fontWeight: "700" }}>{value}</Text></View>; }
function Vote({ label, value, color, styles }: { label: string; value: number; color: string; styles: ReturnType<typeof makeStyles> }) { return <View style={styles.vote}><Text variant="mono" style={{ color, fontSize: 16 }}>{value}</Text><Text variant="muted">{label}</Text></View>; }
function Context({ label, value, sub, styles }: { label: string; value: string; sub?: string; styles: ReturnType<typeof makeStyles> }) { return <View style={styles.context}><Text variant="muted">{label}</Text><Text style={{ fontSize: 12, fontWeight: "700" }}>{value}</Text>{sub ? <Text variant="muted" style={{ fontSize: 9 }}>{sub}</Text> : null}</View>; }

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  between: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 12 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  voteGrid: { flexDirection: "row", gap: 8 },
  vote: { flex: 1, alignItems: "center", gap: 3, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, borderRadius: 10, padding: 9 },
  componentRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 7, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: c.border },
  contextGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  context: { width: "48%", minHeight: 62, gap: 3, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, borderRadius: 10, padding: 9 },
  risk: { gap: 5, borderTopWidth: 1, borderTopColor: c.border, paddingTop: 10 },
  forecast: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8, borderTopWidth: 1, borderTopColor: c.border, paddingTop: 10 },
});
