// Liquid-glass bottom sheet: frosted GlassCard rounded at the top over a dark
// scrim. Same visual language as the rest of the app; used for quick-add forms.
import { ReactNode } from "react";
import { KeyboardAvoidingView, Modal as RNModal, Platform, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { GlassCard } from "@/components/glass/GlassCard";
import { useGlassMode } from "@/components/glass/glass-mode";
import { Text } from "@/components/ui";
import { useTheme } from "@/hooks/use-theme";
import { X } from "@/lib/icons";

export function GlassSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const light = useGlassMode() === "light";
  return (
    <RNModal visible={open} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <KeyboardAvoidingView style={styles.wrap} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} accessibilityLabel="Close" />
        <GlassCard radius={24} intensity={44} sheen={0.16} style={[styles.sheet, { paddingBottom: insets.bottom + 18 }]}>
          {/* Extra frosted tint so form text stays legible. */}
          <View style={[StyleSheet.absoluteFill, { backgroundColor: light ? "rgba(255,255,255,0.55)" : "rgba(7,12,26,0.5)" }]} pointerEvents="none" />
          <View style={[styles.grabber, { backgroundColor: colors.borderHover }]} />
          <View style={styles.header}>
            <Text variant="title" style={{ fontSize: 17 }}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel="Close">
              <X color={colors.textMuted} size={20} />
            </Pressable>
          </View>
          {children}
        </GlassCard>
      </KeyboardAvoidingView>
    </RNModal>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.55)" },
  sheet: { borderBottomLeftRadius: 0, borderBottomRightRadius: 0, paddingHorizontal: 20, paddingTop: 12, gap: 12 },
  grabber: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, marginBottom: 6 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 2 },
});
