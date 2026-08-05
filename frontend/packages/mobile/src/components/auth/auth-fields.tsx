// Form controls shared by the sign-in/sign-up form and the password-recovery
// card. They live here rather than in AuthExperience so ForgotPasswordCard can
// use them without importing the screen that renders it (a cycle Metro would
// resolve to `undefined` at module-init time).
import { LinearGradient } from "expo-linear-gradient";
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, TextInput, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { Text } from "@/components/ui";
import { colors, fonts, radii } from "@/constants/theme";
import { ArrowRight, Eye, EyeOff } from "@/lib/icons";

export function Field({
  label,
  ...props
}: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={{ gap: 6 }}>
      <Text variant="secondary" style={{ fontSize: 13 }}>
        {label}
      </Text>
      <GlassCard radius={12} intensity={16} sheen={0.06}>
        <TextInput
          style={styles.input}
          placeholderTextColor={colors.textMuted}
          accessibilityLabel={label}
          {...props}
        />
      </GlassCard>
    </View>
  );
}

export function PasswordField({
  value,
  onChangeText,
  label = "Password",
  autoComplete = "password",
}: {
  value: string;
  onChangeText: (v: string) => void;
  label?: string;
  autoComplete?: React.ComponentProps<typeof TextInput>["autoComplete"];
}) {
  const [hidden, setHidden] = useState(true);
  return (
    <View style={{ gap: 6 }}>
      <Text variant="secondary" style={{ fontSize: 13 }}>
        {label}
      </Text>
      <GlassCard radius={12} intensity={16} sheen={0.06}>
        <View style={styles.pwRow}>
          <TextInput
            style={[styles.input, { flex: 1 }]}
            placeholderTextColor={colors.textMuted}
            accessibilityLabel={label}
            placeholder="••••••••"
            secureTextEntry={hidden}
            autoComplete={autoComplete}
            autoCapitalize="none"
            value={value}
            onChangeText={onChangeText}
          />
          <Pressable
            onPress={() => setHidden((h) => !h)}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={hidden ? "Show password" : "Hide password"}
            style={styles.pwToggle}
          >
            {hidden ? (
              <Eye color={colors.textMuted} size={18} />
            ) : (
              <EyeOff color={colors.primary} size={18} />
            )}
          </Pressable>
        </View>
      </GlassCard>
    </View>
  );
}

export function PrimaryButton({
  label,
  onPress,
  loading,
}: {
  label: string;
  onPress: () => void;
  loading?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ busy: loading, disabled: loading }}
      style={({ pressed }) => [
        styles.primaryBtn,
        (pressed || loading) && { opacity: 0.9, transform: [{ scale: 0.99 }] },
      ]}
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
          <Text style={styles.primaryText}>{label}</Text>
          <ArrowRight color={colors.primaryForeground} size={18} />
        </>
      )}
    </Pressable>
  );
}

export function GlassButton({
  label,
  onPress,
  disabled,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [{ borderRadius: radii.btn }, pressed && { opacity: 0.8 }]}
    >
      <GlassCard radius={radii.btn} intensity={20} sheen={0.12} style={styles.glassBtn}>
        <Text style={styles.glassBtnText}>{label}</Text>
      </GlassCard>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  input: {
    minHeight: 50,
    paddingHorizontal: 14,
    color: colors.textPrimary,
    fontSize: 15,
    fontFamily: fonts.sans,
  },
  pwRow: { flexDirection: "row", alignItems: "center" },
  pwToggle: { paddingHorizontal: 14, height: 50, alignItems: "center", justifyContent: "center" },

  primaryBtn: {
    minHeight: 52,
    borderRadius: radii.btn,
    overflow: "hidden",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 2,
  },
  primaryText: {
    color: colors.primaryForeground,
    fontWeight: "800",
    fontSize: 16,
    fontFamily: fonts.sans,
  },

  glassBtn: { minHeight: 52, alignItems: "center", justifyContent: "center" },
  glassBtnText: {
    color: colors.textPrimary,
    fontWeight: "600",
    fontSize: 15,
    fontFamily: fonts.sans,
  },
});
