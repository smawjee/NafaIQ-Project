// Thin progress bar used by goals, budgets, XP, etc. Theme-aware defaults.
import { View } from "react-native";

import { useTheme } from "@/hooks/use-theme";

export function ProgressBar({
  value,
  color,
  height = 8,
  track,
}: {
  value: number; // 0..1
  color?: string;
  height?: number;
  track?: string;
}) {
  const { colors } = useTheme();
  const pct = Math.max(0, Math.min(1, value));
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ now: Math.round(pct * 100), min: 0, max: 100 }}
      style={{ height, borderRadius: height / 2, backgroundColor: track ?? colors.surfaceAlt, overflow: "hidden" }}
    >
      <View style={{ width: `${pct * 100}%`, height: "100%", backgroundColor: color ?? colors.primary }} />
    </View>
  );
}
