// Standard screen wrapper: liquid-glass backdrop + safe-area + optional scroll +
// Avenir header. Theme-aware via GlassScreen; pass `dark` to pin the dark glass
// for screens still on the static dark palette.
import { ReactNode } from "react";
import { Platform, ScrollView, StyleSheet, View } from "react-native";
import { Edge, SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Text } from "@/components/ui";
import { fonts } from "@/constants/theme";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

export function Screen({
  children,
  title,
  subtitle,
  scroll = true,
  edges = ["top", "left", "right"],
  dark,
}: {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  scroll?: boolean;
  edges?: Edge[];
  dark?: boolean;
}) {
  const header = title ? (
    <View style={styles.header}>
      <Text variant="display" style={{ fontFamily: AVENIR }}>{title}</Text>
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
});
