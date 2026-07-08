// Shared liquid-glass buttons used across the app. GlassButton = frosted
// secondary surface; GlassPrimaryButton = teal gradient primary CTA. Both have
// a subtle press scale for a physical feel.
import { LinearGradient } from "expo-linear-gradient";
import { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, type ViewStyle } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { useGlassMode } from "@/components/glass/glass-mode";
import { Text } from "@/components/ui";
import { colors, fonts, radii } from "@/constants/theme";

export function GlassButton({
  label,
  onPress,
  icon,
  disabled,
  style,
  compact,
}: {
  label: string;
  onPress?: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  style?: ViewStyle;
  compact?: boolean;
}) {
  const light = useGlassMode() === "light";
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [{ borderRadius: radii.btn }, style, pressed && styles.pressed, disabled && { opacity: 0.5 }]}
    >
      <GlassCard radius={radii.btn} intensity={20} sheen={0.12} style={[styles.btn, compact && styles.compact]}>
        {icon}
        <Text style={[styles.glassLabel, { color: light ? "#0f172a" : "#fff" }]}>{label}</Text>
      </GlassCard>
    </Pressable>
  );
}

export function GlassPrimaryButton({
  label,
  onPress,
  icon,
  loading,
  style,
  compact,
}: {
  label: string;
  onPress?: () => void;
  icon?: ReactNode;
  loading?: boolean;
  style?: ViewStyle;
  compact?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ busy: loading }}
      style={({ pressed }) => [styles.primary, compact && styles.compact, style, pressed && styles.pressed]}
    >
      <LinearGradient
        colors={["#2DF2C4", colors.primary]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      {loading ? (
        <ActivityIndicator color={colors.primaryForeground} />
      ) : (
        <>
          {icon}
          <Text style={styles.primaryLabel}>{label}</Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: { minHeight: 46, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, paddingHorizontal: 14 },
  compact: { minHeight: 40 },
  glassLabel: { color: colors.textPrimary, fontWeight: "600", fontSize: 13.5, fontFamily: fonts.sans },
  primary: {
    minHeight: 46,
    borderRadius: radii.btn,
    overflow: "hidden",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 16,
  },
  primaryLabel: { color: colors.primaryForeground, fontWeight: "800", fontSize: 14, fontFamily: fonts.sans },
  pressed: { opacity: 0.9, transform: [{ scale: 0.98 }] },
});
