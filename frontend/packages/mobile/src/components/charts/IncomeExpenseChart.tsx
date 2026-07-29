// Grouped income/expense bar chart (react-native-svg) — replaces the web
// Recharts version. Green = income, red = expense, per month.
import { View } from "react-native";
import Svg, { G, Rect } from "react-native-svg";

import { Text } from "@/components/ui";
import { colors } from "@/constants/theme";

export function IncomeExpenseChart({
  data,
  width,
  height = 150,
}: {
  data: { month: string; income: number; expense: number }[];
  width: number;
  height?: number;
}) {
  const max = Math.max(...data.flatMap((d) => [d.income, d.expense])) || 1;
  const n = data.length || 1;
  const groupW = width / n;
  const barW = Math.max(4, groupW * 0.28);

  return (
    <View>
      <Svg width={width} height={height} accessibilityRole="image" accessibilityLabel="Income vs expense bar chart">
        {data.map((d, i) => {
          const cx = i * groupW + groupW / 2;
          const inH = (d.income / max) * height;
          const exH = (d.expense / max) * height;
          return (
            <G key={d.month}>
              <Rect x={cx - barW - 1} y={height - inH} width={barW} height={inH} rx={2} fill={colors.bull} />
              <Rect x={cx + 1} y={height - exH} width={barW} height={exH} rx={2} fill={colors.bear} />
            </G>
          );
        })}
      </Svg>
      <View style={{ flexDirection: "row", marginTop: 4 }}>
        {data.map((d) => (
          <Text key={d.month} variant="muted" style={{ flex: 1, textAlign: "center", fontSize: 11 }}>
            {d.month}
          </Text>
        ))}
      </View>
    </View>
  );
}
