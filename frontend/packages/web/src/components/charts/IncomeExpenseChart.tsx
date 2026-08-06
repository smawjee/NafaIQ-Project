import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useLang } from "@/hooks/use-lang";
import { useChartTheme } from "@/components/charts/chart-theme";

export function IncomeExpenseChart({
  data,
}: {
  data: { month: string; income: number; expense: number }[];
}) {
  const ct = useChartTheme();
  const { t } = useLang();
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={ct.grid} vertical={false} />
        <XAxis
          dataKey="month"
          // Demo series carries bare month names ("Jan"); the API sends
          // "YYYY-MM", which has no dictionary entry and passes through.
          tickFormatter={(v) => t(String(v))}
          tick={{ fill: ct.tick, fontSize: 11 }}
          axisLine={{ stroke: ct.grid }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: ct.tick, fontSize: 10 }}
          width={48}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => (v / 1000).toFixed(0) + "k"}
        />
        <Tooltip
          contentStyle={ct.tooltip}
          labelStyle={{ color: ct.tooltipLabel }}
          cursor={{ fill: ct.cursorBar, fillOpacity: ct.light ? 1 : 0.4 }}
        />
        {!ct.light && <Legend wrapperStyle={{ fontSize: 12 }} />}
        <Bar
          dataKey="income"
          name={t("In")}
          fill={ct.teal}
          radius={[3, 3, 0, 0]}
          isAnimationActive
          animationBegin={0}
          animationDuration={900}
          animationEasing="ease-out"
        />
        <Bar
          dataKey="expense"
          name={t("Out")}
          fill={ct.expense}
          radius={[3, 3, 0, 0]}
          isAnimationActive
          animationBegin={200}
          animationDuration={900}
          animationEasing="ease-out"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
