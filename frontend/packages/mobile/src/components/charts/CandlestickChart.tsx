// Candlestick chart (react-native-svg) — replaces the web Recharts candle chart.
// Renders OHLC candles with optional moving-average overlays and a volume strip.
import { useMemo } from "react";
import { View } from "react-native";
import Svg, { G, Line, Polyline, Rect } from "react-native-svg";

import { colors } from "@/constants/theme";
import type { Candle } from "@nafaiq/shared";
import { sma } from "@nafaiq/shared";

type MA = { period: number; color: string };

export function CandlestickChart({
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
  const volH = showVolume ? Math.round(height * 0.18) : 0;
  const priceH = height - volH - (showVolume ? 6 : 0);

  const model = useMemo(() => {
    if (data.length === 0) return null;
    const highs = data.map((d) => d.high);
    const lows = data.map((d) => d.low);
    const min = Math.min(...lows);
    const max = Math.max(...highs);
    const span = max - min || 1;
    const n = data.length;
    const slot = width / n;
    const bodyW = Math.max(1, slot * 0.6);
    const yOf = (v: number) => priceH - ((v - min) / span) * priceH;
    const xOf = (i: number) => i * slot + slot / 2;

    const maxVol = Math.max(...data.map((d) => d.volume)) || 1;

    const maLines = mas.map((m) => {
      const vals = sma(data, m.period);
      const pts = vals
        .map((v, i) => (v == null ? null : `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`))
        .filter(Boolean)
        .join(" ");
      return { color: m.color, pts };
    });

    return { min, max, span, slot, bodyW, yOf, xOf, maxVol, maLines };
  }, [data, width, priceH, mas]);

  if (!model) return <View style={{ width, height }} />;

  return (
    <Svg width={width} height={height} accessibilityRole="image" accessibilityLabel="Price candlestick chart">
      {data.map((c, i) => {
        const up = c.close >= c.open;
        const color = up ? colors.bull : colors.bear;
        const x = model.xOf(i);
        const bodyTop = model.yOf(Math.max(c.open, c.close));
        const bodyBottom = model.yOf(Math.min(c.open, c.close));
        const bodyH = Math.max(1, bodyBottom - bodyTop);
        return (
          <G key={i}>
            <Line x1={x} y1={model.yOf(c.high)} x2={x} y2={model.yOf(c.low)} stroke={color} strokeWidth={1} />
            <Rect x={x - model.bodyW / 2} y={bodyTop} width={model.bodyW} height={bodyH} fill={color} />
            {showVolume && (
              <Rect
                x={x - model.bodyW / 2}
                y={height - (c.volume / model.maxVol) * volH}
                width={model.bodyW}
                height={(c.volume / model.maxVol) * volH}
                fill={color}
                opacity={0.35}
              />
            )}
          </G>
        );
      })}
      {model.maLines.map((m, i) =>
        m.pts ? <Polyline key={`ma${i}`} points={m.pts} fill="none" stroke={m.color} strokeWidth={1.4} /> : null,
      )}
    </Svg>
  );
}
