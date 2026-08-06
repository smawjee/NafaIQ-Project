// Standard screen wrapper: liquid-glass backdrop + safe-area + optional scroll +
// Avenir header. Theme-aware via GlassScreen; pass `dark` to pin the dark glass
// for screens still on the static dark palette.
import { ReactNode } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Edge, SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Text } from "@/components/ui";
import { fonts } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { ArrowLeft } from "@/lib/icons";

export function Screen({
  children,
  title,
  subtitle,
  scroll = true,
  edges = ["top", "left", "right"],
  dark,
  back = false,
}: {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  scroll?: boolean;
  edges?: Edge[];
  dark?: boolean;
  /** Show an in-content back button beside the title (matches more.tsx). */
  back?: boolean;
}) {
  const router = useRouter();
  const { colors } = useTheme();
  const header = title ? (
    <View style={styles.header}>
      <View style={styles.titleRow}>
        {back ? (
          <Pressable
            onPress={() => router.back()}
            hitSlop={12}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <ArrowLeft color={colors.textPrimary} size={22} />
          </Pressable>
        ) : null}
        <Text variant="display" style={{ fontFamily: fonts.heading }}>{title}</Text>
      </View>
      {subtitle ? (
        <Text variant="secondary" style={{ marginTop: 2 }}>
          {subtitle}
        </Text>
      ) : null}
    </View>
  ) : null;

  return (
    <GlassScreen dark={dark}>
      <SafeAreaView style={styles.safe} edges={edges}>
        {scroll ? (
          <ScrollView
            contentContainerStyle={styles.content}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {header}
            {children}
          </ScrollView>
        ) : (
          <View style={styles.content}>
            {header}
            {children}
          </View>
        )}
      </SafeAreaView>
    </GlassScreen>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  content: { padding: 16, gap: 16 },
  header: { marginBottom: 4 },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  backBtn: { minWidth: 40, minHeight: 40, alignItems: "center", justifyContent: "center", marginLeft: -10 },
});
