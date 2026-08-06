// NafaIQ brand lockup: the vector "N" mark in a rounded navy tile + the "NafaIQ"
// wordmark in code ("IQ" in primary teal). Fully vector — crisp at any size.
import { StyleSheet, View, type ViewProps } from "react-native";

import { NafaMark } from "@/components/NafaMark";
import { Text } from "@/components/ui";
import { colors, fonts } from "@/constants/theme";

export function Logo({
  size = 40,
  wordmark = true,
  style,
  ...rest
}: ViewProps & { size?: number; wordmark?: boolean }) {
  return (
    <View
      style={[styles.row, style]}
      accessibilityRole="image"
      accessibilityLabel="NafaIQ"
      {...rest}
    >
      <View style={[styles.badge, { width: size, height: size, borderRadius: size * 0.28 }]}>
        <NafaMark size={size * 0.72} />
      </View>
      {wordmark && (
        <Text
          style={{ fontSize: size * 0.62, fontWeight: "800", letterSpacing: -0.5, fontFamily: fonts.heading }}
          accessibilityElementsHidden
          importantForAccessibility="no"
        >
          Nafa
          <Text style={{ color: colors.primary, fontSize: size * 0.62, fontWeight: "800", fontFamily: fonts.heading }}>
            IQ
          </Text>
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  badge: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
