import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useLang } from "@/hooks/use-lang";
import { useChartTheme, DONUT_LIGHT_PALETTE } from "@/components/charts/chart-theme";

export function DonutChart({
  data,
  centerLabel,
  centerValue,
}: {
  data: { name: string; value: number; color: string; amount?: number }[];
  centerLabel?: string;
  centerValue?: string;
}) {
  const ct = useChartTheme();
  const { t } = useLang();
  const lightPalette = DONUT_LIGHT_PALETTE;
  const tdata = data.map((d) => ({ ...d, name: t(d.name) }));

  const renderSliceLabel = (props: {
    cx: number;
    cy: number;
    midAngle: number;
    innerRadius: number;
    outerRadius: number;
    percent: number;
  }) => {
    const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;
    if (percent < 0.12) return null;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const RADIAN = Math.PI / 180;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    return (
      <text
        x={x}
        y={y}
        fill={ct.light ? "#0f172a" : "#ffffff"}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={ct.light ? 13 : 10}
        fontWeight={600}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  const DonutTip = ({ active, payload }: { active?: boolean; payload?: any[] }) => {
    if (!active || !payload?.length) return null;
    const p = payload[0].payload as { name: string; value: number; amount?: number };
    return (
      <div
        style={{
          background: ct.tooltip.background,
          border: ct.tooltip.border,
          borderRadius: 12,
          boxShadow: ct.tooltip.boxShadow,
          padding: "10px 14px",
        }}
      >
        <div style={{ fontSize: 12, color: ct.tooltipLabel, marginBottom: 2 }}>{p.name}</div>
        <div
          style={{
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 16,
            fontWeight: 700,
            color: ct.tooltip.color,
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "0.02em",
          }}
        >
          {p.amount != null ? `PKR ${p.amount.toLocaleString()}` : `${p.value}%`}
        </div>
      </div>
    );
  };

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={tdata}
            dataKey="value"
            nameKey="name"
            innerRadius={62}
            outerRadius={92}
            paddingAngle={3}
            cornerRadius={4}
            stroke={ct.light ? "#ffffff" : "none"}
            strokeWidth={ct.light ? 2 : 0}
            isAnimationActive={false}
            label={renderSliceLabel}
            labelLine={false}
          >
            {data.map((d, i) => (
              <Cell key={i} fill={ct.light ? lightPalette[i % lightPalette.length] : d.color} />
            ))}
          </Pie>
          <Tooltip content={<DonutTip />} cursor={false} />
        </PieChart>
      </ResponsiveContainer>
      {centerValue && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-sm font-bold tabular-nums text-text-primary">
            {centerValue}
          </span>
          {centerLabel && <span className="text-[10px] text-text-muted">{t(centerLabel)}</span>}
        </div>
      )}
    </div>
  );
}
