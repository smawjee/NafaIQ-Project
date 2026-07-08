// Minimal SVG sparkline — the first of the react-native-svg chart primitives
// that replace the web app's Recharts. CandlestickChart / PortfolioAreaChart /
// DonutChart / IncomeExpenseChart will follow the same pattern.
import { useMemo } from "react";
import Svg, { Path } from "react-native-svg";

import { colors } from "@/constants/theme";

export function Sparkline({
  data,
  width = 88,
  height = 28,
  color,
}: {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const { d, stroke } = useMemo(() => {
    if (data.length < 2) return { d: "", stroke: colors.neutral };
    const min = Math.min(...data);
    const max = Math.max(...data);
    const span = max - min || 1;
    const stepX = width / (data.length - 1);
    const points = data.map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const up = data[data.length - 1] >= data[0];
    return {
      d: `M${points.join(" L")}`,
      stroke: color ?? (up ? colors.bull : colors.bear),
    };
  }, [data, width, height, color]);

  return (
    <Svg width={width} height={height} accessibilityRole="image">
      <Path d={d} stroke={stroke} strokeWidth={1.5} fill="none" />
    </Svg>
  );
}
