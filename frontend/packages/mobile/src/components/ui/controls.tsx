// Small reusable controls: filter Chip and Segmented (tab) selector. Theme-aware.
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { Text } from "@/components/ui";
import { radii } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";

export function Chip({
  label,
  active,
  onPress,
  color,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  color?: string;
}) {
  const { colors } = useTheme();
  const c = color ?? colors.primary;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={[
        styles.chip,
        { borderColor: active ? c : colors.border, backgroundColor: active ? c + "22" : "transparent" },
      ]}
    >
      <Text style={{ fontSize: 12, color: active ? c : colors.textSecondary, fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
}

export function ChipRow({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {options.map((o) => (
        <Chip key={o} label={o} active={o === value} onPress={() => onChange(o)} />
      ))}
    </ScrollView>
  );
}

export function Segmented({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  const { colors } = useTheme();
  // Uniform size for every segment so a long label (e.g. "Transactions") and the
  // short ones all render at the same size; shrink the base when there are many
  // segments or a long label so nothing wraps or has to shrink individually.
  const longest = options.reduce((m, o) => Math.max(m, o.length), 0);
  const fontSize = options.length >= 5 || longest >= 10 ? 10.5 : 12;
  return (
    <View style={[styles.segment, { backgroundColor: colors.surfaceAlt }]}>
      {options.map((o) => {
        const active = o === value;
        return (
          <Pressable
            key={o}
            onPress={() => onChange(o)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            style={[styles.segItem, active && { backgroundColor: colors.elevated }]}
          >
            <Text numberOfLines={1} style={{ fontSize, color: active ? colors.textPrimary : colors.textMuted }}>
              {o}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: radii.full, borderWidth: 1, minHeight: 32, justifyContent: "center" },
  row: { gap: 8, paddingVertical: 2 },
  segment: { flexDirection: "row", borderRadius: radii.btn, padding: 3 },
  segItem: { flex: 1, alignItems: "center", paddingVertical: 7, borderRadius: radii.btn - 2 },
});
