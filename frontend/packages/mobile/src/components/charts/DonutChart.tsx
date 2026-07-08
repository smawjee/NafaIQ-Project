// Donut chart (react-native-svg) — replaces the web Recharts donut. Used for
// allocation (sector/stock) and spending breakdown.
import { useMemo } from "react";
import { View } from "react-native";
import Svg, { Circle, G } from "react-native-svg";

import { Text } from "@/components/ui";
import { useTheme } from "@/hooks/use-theme";

export type DonutSegment = { label: string; value: number; color: string };

export function DonutChart({
  segments,
  size = 160,
  strokeWidth = 22,
  centerLabel,
  centerSub,
}: {
  segments: DonutSegment[];
  size?: number;
  strokeWidth?: number;
  centerLabel?: string;
  centerSub?: string;
}) {
  const { colors } = useTheme();
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;

  // Precompute each arc's dash length + offset (prefix sum) without mutation.
  const arcs = useMemo(() => {
    const fracs = segments.map((s) => s.value / total);
    return segments.map((seg, i) => ({
      seg,
      dash: fracs[i] * c,
      offset: fracs.slice(0, i).reduce((a, b) => a + b, 0) * c,
    }));
  }, [segments, total, c]);

  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Svg width={size} height={size} accessibilityRole="image" accessibilityLabel="Allocation donut chart">
        <G rotation={-90} origin={`${size / 2}, ${size / 2}`}>
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.surfaceAlt} strokeWidth={strokeWidth} fill="none" />
          {arcs.map(({ seg, dash, offset }, i) => (
            <Circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              stroke={seg.color}
              strokeWidth={strokeWidth}
              fill="none"
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            />
          ))}
        </G>
      </Svg>
      {centerLabel ? (
        <View style={{ position: "absolute", alignItems: "center", width: size - strokeWidth * 2 - 10 }}>
          <Text
            variant="title"
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.6}
            style={{ fontSize: 17, textAlign: "center" }}
          >
            {centerLabel}
          </Text>
          {centerSub ? <Text variant="muted" numberOfLines={1}>{centerSub}</Text> : null}
        </View>
      ) : null}
    </View>
  );
}
