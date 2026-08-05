// Calibrated base-rate call. Mirrors web
// src/features/signals/SignalRecommendation.tsx: the same probability, the same
// interval, the same bridge line when the indicator posture disagrees.
//
// The number shown is a measured historical frequency for a named cohort, not a
// model score and not a forecast. It is rendered against the measured base rate
// (~47% on PSX), never against 50% — anchoring to a half would make an ordinary
// stock look bearish.
import { StyleSheet, View } from "react-native";

import { Card, Text } from "@/components/ui";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import type { ApiSignalDetail } from "@/lib/signals";

type Recommendation = NonNullable<ApiSignalDetail["recommendation"]>;

const RATING_LABEL: Record<Recommendation["rating"], string> = {
  STRONG_BUY: "Strong Buy",
  BUY: "Buy",
  HOLD: "Hold",
  SELL: "Sell",
  STRONG_SELL: "Strong Sell",
};

const ABSTAIN_COPY: Record<string, string> = {
  INTERVAL_STRADDLES_BASE_RATE:
    "The historical range for this setup spans the market average, so there is no clear edge either way.",
  EDGE_TOO_SMALL_TO_ACT:
    "This setup leaned slightly one way historically, but not by enough to cover trading costs.",
  INSUFFICIENT_COHORT: "Too few comparable cases in PSX history to say anything reliable.",
  NO_CALIBRATION_DATA: "Historical base rates are unavailable right now.",
};

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(0)}%`;
}

function postureDirection(rating?: string | null): "up" | "down" | "flat" {
  if (rating === "Strong Bullish" || rating === "Bullish") return "up";
  if (rating === "Strong Bearish" || rating === "Bearish") return "down";
  return "flat";
}

function callDirection(rating: Recommendation["rating"]): "up" | "down" | "flat" {
  if (rating === "STRONG_BUY" || rating === "BUY") return "up";
  if (rating === "STRONG_SELL" || rating === "SELL") return "down";
  return "flat";
}

// Measured cells span ~0.26-0.70, so a 0-100% axis would compress every real
// difference to nothing. Fixing the domain makes the gap legible.
const DOMAIN_LO = 0.3;
const DOMAIN_HI = 0.7;
const clampPct = (p: number) =>
  Math.min(100, Math.max(0, ((p - DOMAIN_LO) / (DOMAIN_HI - DOMAIN_LO)) * 100));

export function SignalRecommendationCard({ signal }: { signal?: ApiSignalDetail | null }) {
  const { colors } = useTheme();
  const { t } = useLang();

  const rec = signal?.recommendation;
  if (!rec) return null;

  const direction = callDirection(rec.rating);
  const accent =
    direction === "up" ? colors.bull : direction === "down" ? colors.bear : colors.textSecondary;

  const posture = signal?.technical_setup?.rating ?? null;
  const disagrees =
    postureDirection(posture) !== "flat" &&
    direction !== "flat" &&
    postureDirection(posture) !== direction;

  const hasNumbers = rec.p !== null && rec.p_lower !== null && rec.p_upper !== null;

  return (
    <Card style={{ gap: 10 }}>
      <View style={styles.header}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text variant="title">{t("Recommendation")}</Text>
          <Text variant="muted" style={{ fontSize: 11 }}>
            {t("Based on")} {rec.sample_size.toLocaleString()}{" "}
            {t("comparable cases in PSX history")}
          </Text>
        </View>
        <View
          accessibilityRole="text"
          accessibilityLabel={`${t("Recommendation")}: ${t(RATING_LABEL[rec.rating])}`}
          style={[styles.badge, { borderColor: accent, backgroundColor: colors.glassFill }]}
        >
          <Text variant="body" style={{ color: accent, fontWeight: "700", fontSize: 13 }}>
            {t(RATING_LABEL[rec.rating])}
          </Text>
        </View>
      </View>

      {hasNumbers && rec.base_rate !== null ? (
        <View style={{ gap: 6 }}>
          <View style={styles.row}>
            <Text variant="muted" style={{ fontSize: 12, flex: 1 }}>
              {pct(rec.p)} {t(rec.event)}
            </Text>
            <Text variant="mono" style={{ fontSize: 11, color: colors.textSecondary }}>
              {t("vs")} {pct(rec.base_rate)} {t("typical")}
            </Text>
          </View>

          {/* Confidence interval against the measured base rate. */}
          <View style={[styles.track, { backgroundColor: colors.border }]}>
            <View
              style={[
                styles.band,
                {
                  backgroundColor: accent,
                  left: `${clampPct(rec.p_lower as number)}%`,
                  width: `${Math.max(
                    1.5,
                    clampPct(rec.p_upper as number) - clampPct(rec.p_lower as number),
                  )}%`,
                },
              ]}
            />
            <View
              style={[
                styles.baseTick,
                { backgroundColor: colors.textSecondary, left: `${clampPct(rec.base_rate)}%` },
              ]}
            />
          </View>
          <View style={styles.row}>
            <Text variant="muted" style={{ fontSize: 10, flex: 1 }}>
              {t("Range")} {pct(rec.p_lower)}–{pct(rec.p_upper)}
            </Text>
            <Text variant="muted" style={{ fontSize: 10 }}>
              {t("95% confidence")}
            </Text>
          </View>
        </View>
      ) : null}

      {rec.basis ? (
        <Text variant="muted" style={{ fontSize: 11 }}>
          {t("Measured across")} {rec.basis}.
        </Text>
      ) : null}

      {rec.rating === "HOLD" && rec.abstain_reason ? (
        <View style={[styles.note, { backgroundColor: colors.glassFill, borderColor: colors.border }]}>
          <Text variant="muted" style={{ fontSize: 11 }}>
            {t(ABSTAIN_COPY[rec.abstain_reason] ?? "No clear edge in the historical record.")}
          </Text>
        </View>
      ) : null}

      {disagrees && posture ? (
        <View style={[styles.note, { backgroundColor: colors.glassFill, borderColor: accent }]}>
          <Text variant="muted" style={{ fontSize: 11 }}>
            {t("Indicators currently read")} {t(posture)}
            {t(", but this is about what happened next: on PSX, stocks in this state went on to rise")}{" "}
            {pct(rec.p)} {t("of the time over the following")} {rec.horizon_sessions}{" "}
            {t("sessions. Measured, not a promise.")}
          </Text>
        </View>
      ) : null}

      <View style={styles.row}>
        {rec.round_trip_cost !== null ? (
          <Text variant="muted" style={{ fontSize: 11, flex: 1 }}>
            {t("Est. round-trip cost")}{" "}
            <Text variant="mono" style={{ fontSize: 11, color: colors.textSecondary }}>
              {(rec.round_trip_cost * 100).toFixed(2)}%
            </Text>
          </Text>
        ) : null}
        {rec.suggested_stop_pct !== null ? (
          <Text variant="muted" style={{ fontSize: 11 }}>
            {t("Suggested stop")}{" "}
            <Text variant="mono" style={{ fontSize: 11, color: colors.textSecondary }}>
              {(rec.suggested_stop_pct * 100).toFixed(1)}%
            </Text>
          </Text>
        ) : null}
      </View>

      {rec.asymmetric ? (
        <Text variant="muted" style={{ fontSize: 10, fontStyle: "italic" }}>
          {t(
            "Buy calls require stronger evidence than sell calls — on PSX the sell-side signal has historically been the more reliable of the two.",
          )}
        </Text>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  badge: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    minHeight: 32,
    justifyContent: "center",
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  track: { height: 4, borderRadius: 2, width: "100%", position: "relative" },
  band: { position: "absolute", top: 0, height: 4, borderRadius: 2 },
  baseTick: { position: "absolute", top: -4, width: 1, height: 12 },
  note: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 10, padding: 10 },
});
