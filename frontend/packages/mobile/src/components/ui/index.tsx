// Shared themed primitives — RN equivalents of the web Card / StatCard / Change
// / SignalBadge / Button. Theme-aware: colors come from useTheme() (light/dark).
import { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text as RNText,
  type TextProps as RNTextProps,
  View,
  type ViewProps,
} from "react-native";

import { fonts, radii, signalColorFor, type ThemeColors } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import type { Signal } from "@nafaiq/shared";

/* ---------------------------------- Text --------------------------------- */
type TextVariant = "display" | "title" | "body" | "secondary" | "muted" | "mono" | "urdu";

function textStyle(variant: TextVariant, c: ThemeColors): object {
  switch (variant) {
    case "display":
      return { fontSize: 26, fontWeight: "700", color: c.textPrimary };
    case "title":
      return { fontSize: 18, fontWeight: "600", color: c.textPrimary };
    case "secondary":
      return { fontSize: 14, color: c.textSecondary };
    case "muted":
      return { fontSize: 12, color: c.textMuted };
    case "mono":
      return { fontSize: 14, color: c.textPrimary, fontFamily: fonts.mono, fontVariant: ["tabular-nums"] };
    case "urdu":
      return { fontSize: 18, color: c.textPrimary, fontFamily: fonts.urdu, writingDirection: "rtl" };
    default:
      return { fontSize: 15, color: c.textPrimary };
  }
}

export function Text({ variant = "body", style, ...rest }: RNTextProps & { variant?: TextVariant }) {
  const { colors } = useTheme();
  return <RNText style={[textStyle(variant, colors), style]} {...rest} />;
}

/* ---------------------------------- Card --------------------------------- */
export function Card({ style, ...rest }: ViewProps) {
  const { colors } = useTheme();
  return <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }, style]} {...rest} />;
}

/* -------------------------------- StatCard ------------------------------- */
export function StatCard({ label, value, delta }: { label: string; value: string; delta?: number }) {
  return (
    <Card style={styles.statCard}>
      <Text variant="muted">{label}</Text>
      <Text variant="title" style={{ fontFamily: fonts.mono, marginTop: 4 }}>
        {value}
      </Text>
      {delta !== undefined && <Change pct={delta} />}
    </Card>
  );
}

/* --------------------------------- Change -------------------------------- */
export function Change({ pct }: { pct: number }) {
  const { colors } = useTheme();
  const up = pct >= 0;
  const c = up ? colors.bull : colors.bear;
  return (
    <Text
      style={{ color: c, fontFamily: fonts.mono, fontSize: 13, marginTop: 2 }}
      accessibilityLabel={`${up ? "up" : "down"} ${Math.abs(pct).toFixed(2)} percent`}
    >
      {up ? "▲" : "▼"} {Math.abs(pct).toFixed(2)}%
    </Text>
  );
}

/* ------------------------------- SignalBadge ----------------------------- */
export function SignalBadge({ signal }: { signal: Signal }) {
  const { colors } = useTheme();
  const { t } = useLang();
  const c = signalColorFor(colors)[signal] ?? colors.neutral;
  const strong = signal === "STRONG BUY" || signal === "STRONG SELL";
  return (
    <View style={[styles.badge, { backgroundColor: c + "22", borderColor: c + "55" }]}>
      <Text style={{ color: c, fontSize: 10, fontWeight: strong ? "800" : "700", letterSpacing: 0.3, textAlign: "center" }}>
        {t(signal).toUpperCase()}
      </Text>
    </View>
  );
}

/* --------------------------------- Button -------------------------------- */
type ButtonVariant = "primary" | "outline" | "ghost";

export function Button({
  title,
  onPress,
  variant = "primary",
  loading,
  disabled,
  icon,
}: {
  title: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  loading?: boolean;
  disabled?: boolean;
  icon?: ReactNode;
}) {
  const { colors } = useTheme();
  const isDisabled = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      style={({ pressed }) => [
        styles.btn,
        variant === "primary" && { backgroundColor: colors.primary },
        variant === "outline" && { borderWidth: 1, borderColor: colors.borderHover },
        variant === "ghost" && { backgroundColor: "transparent" },
        (pressed || isDisabled) && { opacity: 0.7 },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === "primary" ? colors.primaryForeground : colors.primary} />
      ) : (
        <>
          {icon}
          <Text
            style={{
              fontWeight: "600",
              color: variant === "primary" ? colors.primaryForeground : colors.textPrimary,
            }}
          >
            {title}
          </Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 1, borderRadius: radii.card, padding: 16 },
  statCard: { flex: 1, minWidth: 150 },
  badge: { alignSelf: "flex-start", minWidth: 84, alignItems: "center", justifyContent: "center", borderWidth: 1, borderRadius: radii.full, paddingHorizontal: 8, paddingVertical: 3 },
  btn: { minHeight: 44, borderRadius: radii.btn, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, paddingHorizontal: 16 },
});
