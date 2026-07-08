// Area chart (react-native-svg) — replaces the web Recharts portfolio area
// chart. Optional benchmark line (e.g. KSE-100) drawn dashed on top.
import { useMemo } from "react";
import Svg, { Defs, LinearGradient, Path, Stop } from "react-native-svg";

import { colors } from "@/constants/theme";

export function AreaChart({
  data,
  benchmark,
  width,
  height = 180,
  color = colors.primary,
}: {
  data: number[];
  benchmark?: number[];
  width: number;
  height?: number;
  color?: string;
}) {
  const { area, line, bench } = useMemo(() => {
    const all = benchmark ? [...data, ...benchmark] : data;
    if (all.length < 2) return { area: "", line: "", bench: "" };
    const min = Math.min(...all);
    const max = Math.max(...all);
    const span = max - min || 1;
    const stepX = (n: number) => width / (n - 1);
    const path = (series: number[]) => {
      const sx = stepX(series.length);
      return series
        .map((v, i) => `${(i * sx).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
        .join(" L");
    };
    const linePts = path(data);
    return {
      line: `M${linePts}`,
      area: `M0,${height} L${linePts} L${width},${height} Z`,
      bench: benchmark ? `M${path(benchmark)}` : "",
    };
  }, [data, benchmark, width, height]);

  return (
    <Svg width={width} height={height} accessibilityRole="image" accessibilityLabel="Performance area chart">
      <Defs>
        <LinearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={color} stopOpacity={0.35} />
          <Stop offset="1" stopColor={color} stopOpacity={0} />
        </LinearGradient>
      </Defs>
      {area ? <Path d={area} fill="url(#areaFill)" /> : null}
      {line ? <Path d={line} stroke={color} strokeWidth={2} fill="none" /> : null}
      {bench ? <Path d={bench} stroke={colors.textMuted} strokeWidth={1.4} strokeDasharray="4 4" fill="none" /> : null}
    </Svg>
  );
}
