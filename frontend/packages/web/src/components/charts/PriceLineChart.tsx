import { useId } from "react";
import {
  Area,
  Bar,
  Cell,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type Candle, fmtNum, sma } from "@/lib/data";
import { useLang } from "@/hooks/use-lang";
import { useChartTheme } from "@/components/charts/chart-theme";

export function PriceLineChart({
  data,
  height = 480,
  mas = ["MA20", "MA50", "MA100"],
  maSeries,
  currentPrice,
}: {
  data: Candle[];
  height?: number;
  mas?: string[];
  maSeries?: { ma20: (number | null)[]; ma50: (number | null)[]; ma100: (number | null)[]; ma200: (number | null)[] };
  currentPrice?: number;
}) {
  const ct = useChartTheme();
  const { t } = useLang();
  const priceLineGradientId = useId();
  if (!data || data.length === 0) {
    return (
      <div
        className="flex h-full w-full items-center justify-center text-xs text-text-muted"
        style={{ height: height >= 9999 ? "100%" : height }}
      >
        —
      </div>
    );
  }
  const ma20 = maSeries?.ma20 ?? sma(data, 20);
  const ma50 = maSeries?.ma50 ?? sma(data, 50);
  const ma100 = maSeries?.ma100 ?? sma(data, 100);
  const ma200 = maSeries?.ma200 ?? sma(data, 200);
  const enriched = data.map((c, i) => ({
    date: c.date,
    close: c.close,
    volume: c.volume,
    ma20: ma20[i],
    ma50: ma50[i],
    ma100: ma100[i],
    ma200: ma200[i],
  }));
  const maxVol = Math.max(...data.map((d) => d.volume));
  const lows = Math.min(...data.map((d) => d.low));
  const highs = Math.max(...data.map((d) => d.high));
  const pad = (highs - lows) * 0.08;

  return (
    <ResponsiveContainer width="100%" height={height >= 9999 ? "100%" : height}>
      <ComposedChart data={enriched} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={priceLineGradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ct.teal} stopOpacity={ct.light ? 0.18 : 0.32} />
            <stop offset="100%" stopColor={ct.teal} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={ct.grid} vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: ct.tick, fontSize: 10 }}
          minTickGap={48}
          axisLine={{ stroke: ct.grid }}
          tickLine={false}
        />
        <YAxis
          yAxisId="price"
          orientation="right"
          domain={[lows - pad, highs + pad]}
          tick={{ fill: ct.tick, fontSize: 10 }}
          width={56}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => fmtNum(v, 0)}
        />
        <YAxis yAxisId="vol" domain={[0, maxVol * 5]} hide />
        <Tooltip
          contentStyle={ct.tooltip}
          labelStyle={{ color: ct.tooltipLabel }}
          formatter={(v: number) => fmtNum(v)}
          cursor={{ stroke: ct.benchmark, strokeDasharray: "4 4" }}
        />
        <Bar yAxisId="vol" dataKey="volume" isAnimationActive={false}>
          {enriched.map((c, i) => (
            <Cell key={i} fill={ct.benchmark} fillOpacity={0.18} />
          ))}
        </Bar>
        <Area
          yAxisId="price"
          type="monotone"
          dataKey="close"
          name={t("Price")}
          stroke={ct.teal}
          strokeWidth={2}
          fill={`url(#${priceLineGradientId})`}
          isAnimationActive={false}
        />
        {mas.includes("MA20") && (
          <Line yAxisId="price" dataKey="ma20" name="MA20" stroke="#f59e0b" dot={false} strokeWidth={1.2} isAnimationActive={false} />
        )}
        {mas.includes("MA50") && (
          <Line yAxisId="price" dataKey="ma50" name="MA50" stroke="#3b82f6" dot={false} strokeWidth={1.2} isAnimationActive={false} />
        )}
        {mas.includes("MA100") && (
          <Line yAxisId="price" dataKey="ma100" name="MA100" stroke="#ef4444" dot={false} strokeWidth={1.2} isAnimationActive={false} />
        )}
        {mas.includes("MA200") && (
          <Line yAxisId="price" dataKey="ma200" name="MA200" stroke="#8b5cf6" dot={false} strokeWidth={1.2} isAnimationActive={false} />
        )}
        {currentPrice !== undefined && (
          <ReferenceLine
            y={currentPrice}
            stroke={ct.teal}
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: `PKR ${currentPrice.toFixed(2)}`,
              position: "right",
              fill: ct.teal,
              fontSize: 10,
            }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
