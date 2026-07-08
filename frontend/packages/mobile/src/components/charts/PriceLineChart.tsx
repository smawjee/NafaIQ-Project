// Price line/area chart (react-native-svg) — the "line" counterpart to the
// candlestick view (web PriceLineChart). Close-price area + MA overlays + volume.
import { useMemo } from "react";
import { View } from "react-native";
import Svg, { Defs, LinearGradient, Path, Polyline, Rect, Stop } from "react-native-svg";

import { useTheme } from "@/hooks/use-theme";
import type { Candle } from "@nafaiq/shared";
import { sma } from "@nafaiq/shared";

type MA = { period: number; color: string };

export function PriceLineChart({
  data,
  width,
  height = 220,
  mas = [],
  showVolume = true,
}: {
  data: Candle[];
  width: number;
  height?: number;
  mas?: MA[];
  showVolume?: boolean;
}) {
  const { colors } = useTheme();
  const volH = showVolume ? Math.round(height * 0.18) : 0;
  const priceH = height - volH - (showVolume ? 6 : 0);

  const model = useMemo(() => {
    if (data.length < 2) return null;
    const lows = Math.min(...data.map((d) => d.low));
    const highs = Math.max(...data.map((d) => d.high));
    const pad = (highs - lows) * 0.08 || 1;
    const min = lows - pad;
    const span = highs + pad - min || 1;
    const n = data.length;
    const stepX = width / (n - 1);
    const slot = width / n;
    const yOf = (v: number) => priceH - ((v - min) / span) * priceH;
    const xOf = (i: number) => i * stepX;

    const linePts = data.map((c, i) => `${xOf(i).toFixed(1)},${yOf(c.close).toFixed(1)}`);
    const line = `M${linePts.join(" L")}`;
    const area = `M0,${priceH} L${linePts.join(" L")} L${width},${priceH} Z`;

    const maLines = mas.map((m) => {
      const vals = sma(data, m.period);
      const pts = vals
        .map((v, i) => (v == null ? null : `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`))
        .filter(Boolean)
        .join(" ");
      return { color: m.color, pts };
    });

    const maxVol = Math.max(...data.map((d) => d.volume)) || 1;
    return { line, area, maLines, maxVol, slot };
  }, [data, width, priceH, mas]);

  if (!model) return <View style={{ width, height }} />;

  return (
    <Svg width={width} height={height} accessibilityRole="image" accessibilityLabel="Price line chart">
      <Defs>
        <LinearGradient id="priceLineFill" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={colors.primary} stopOpacity={0.3} />
          <Stop offset="1" stopColor={colors.primary} stopOpacity={0} />
        </LinearGradient>
      </Defs>
      {showVolume &&
        data.map((c, i) => (
          <Rect
            key={i}
            x={i * model.slot + model.slot * 0.15}
            y={height - (c.volume / model.maxVol) * volH}
            width={model.slot * 0.7}
            height={(c.volume / model.maxVol) * volH}
            fill={colors.neutral}
            opacity={0.25}
          />
        ))}
      <Path d={model.area} fill="url(#priceLineFill)" />
      <Path d={model.line} stroke={colors.primary} strokeWidth={2} fill="none" />
      {model.maLines.map((m, i) =>
        m.pts ? <Polyline key={`ma${i}`} points={m.pts} fill="none" stroke={m.color} strokeWidth={1.3} /> : null,
      )}
    </Svg>
  );
}
