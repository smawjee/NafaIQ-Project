import { useId } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useLang } from "@/hooks/use-lang";
import { useChartTheme } from "@/components/charts/chart-theme";

export function PortfolioAreaChart({
  data,
  height = 300,
  showBenchmark = true,
}: {
  data: { label: string; value: number; benchmark: number }[];
  height?: number;
  showBenchmark?: boolean;
}) {
  const ct = useChartTheme();
  const { t } = useLang();
  const tealFillGradientId = useId();
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={tealFillGradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ct.teal} stopOpacity={ct.light ? 0.22 : 0.4} />
            <stop offset="100%" stopColor={ct.teal} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={ct.grid} vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: ct.tick, fontSize: 11 }}
          axisLine={{ stroke: ct.grid }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: ct.tick, fontSize: 10 }}
          width={56}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => (v / 1000).toFixed(0) + "k"}
        />
        <Tooltip contentStyle={ct.tooltip} labelStyle={{ color: ct.tooltipLabel }} />
        <Area
          type="monotone"
          dataKey="value"
          name={t("Portfolio")}
          stroke={ct.teal}
          strokeWidth={2}
          fill={`url(#${tealFillGradientId})`}
          isAnimationActive={false}
        />
        {showBenchmark && (
          <Line
            type="monotone"
            dataKey="benchmark"
            name="KSE-100"
            stroke={ct.benchmark}
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={false}
            isAnimationActive={false}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
