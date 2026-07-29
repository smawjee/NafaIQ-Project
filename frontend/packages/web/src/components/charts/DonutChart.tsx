import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useLang } from "@/hooks/use-lang";
import { useChartTheme, DONUT_LIGHT_PALETTE } from "@/components/charts/chart-theme";

const DONUT_INNER_RADIUS = 62;
const DONUT_OUTER_RADIUS = 92;
const LABEL_SAFE_PADDING = 18;
const LABEL_MIN_PERCENT = 0.12;

type DonutDatum = { name: string; value: number; color: string; amount?: number };
type TooltipMode = "floating" | "center";

function clampLabel(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function DonutChart({
  data,
  centerLabel,
  centerValue,
  showSliceLabels = true,
  height = 220,
  showTooltip = true,
  tooltipMode = "floating",
}: {
  data: DonutDatum[];
  centerLabel?: string;
  centerValue?: string;
  showSliceLabels?: boolean;
  height?: number;
  showTooltip?: boolean;
  tooltipMode?: TooltipMode;
}) {
  const ct = useChartTheme();
  const { t } = useLang();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const lightPalette = DONUT_LIGHT_PALETTE;
  const tdata = data.map((d) => ({ ...d, name: t(d.name) }));
  const activeSlice = activeIndex == null ? null : tdata[activeIndex];
  const useCenterTooltip = showTooltip && tooltipMode === "center" && activeSlice;

  const renderSliceLabel = (props: {
    cx: number;
    cy: number;
    midAngle: number;
    innerRadius: number;
    outerRadius: number;
    percent: number;
  }) => {
    const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;
    if (percent < LABEL_MIN_PERCENT) return null;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const RADIAN = Math.PI / 180;
    const rawX = cx + radius * Math.cos(-midAngle * RADIAN);
    const rawY = cy + radius * Math.sin(-midAngle * RADIAN);
    const chartMin = LABEL_SAFE_PADDING;
    const chartMax = cy * 2 - LABEL_SAFE_PADDING;
    const x = clampLabel(rawX, chartMin, cx * 2 - LABEL_SAFE_PADDING);
    const y = clampLabel(rawY, chartMin, chartMax);

    return (
      <text
        x={x}
        y={y}
        fill={ct.light ? "#0f172a" : "#ffffff"}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={12}
        fontWeight={600}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  const DonutTip = ({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: { payload: DonutDatum }[];
  }) => {
    if (!active || !payload?.length) return null;
    const p = payload[0].payload as DonutDatum;
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
    <div className="relative [&_.recharts-sector]:outline-none [&_.recharts-sector:focus]:outline-none">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={tdata}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={DONUT_INNER_RADIUS}
            outerRadius={DONUT_OUTER_RADIUS}
            paddingAngle={3}
            cornerRadius={4}
            stroke={ct.light ? "#ffffff" : "none"}
            strokeWidth={ct.light ? 2 : 0}
            isAnimationActive={false}
            label={showSliceLabels ? renderSliceLabel : undefined}
            labelLine={false}
            rootTabIndex={-1}
            onMouseEnter={(_, index) => setActiveIndex(index)}
            onMouseLeave={() => setActiveIndex(null)}
          >
            {data.map((d, i) => {
              const active = activeIndex === i;
              const inactive = activeIndex != null && !active;
              return (
                <Cell
                  key={i}
                  fill={ct.light ? lightPalette[i % lightPalette.length] : d.color}
                  className="outline-none transition-opacity duration-150 focus:outline-none"
                  opacity={inactive ? 0.42 : 1}
                  style={{ filter: active ? "brightness(1.12)" : undefined, outline: "none" }}
                />
              );
            })}
          </Pie>
          {showTooltip && tooltipMode === "floating" && (
            <Tooltip content={<DonutTip />} cursor={false} offset={18} />
          )}
        </PieChart>
      </ResponsiveContainer>
      {(centerValue || useCenterTooltip) && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
          {useCenterTooltip ? (
            <>
              <span className="max-w-[104px] truncate text-[11px] font-semibold leading-tight text-text-primary">
                {activeSlice.name}
              </span>
              <span className="mt-0.5 max-w-[104px] truncate font-mono text-[12px] font-bold tabular-nums leading-tight text-text-primary">
                {activeSlice.amount != null
                  ? `PKR ${activeSlice.amount.toLocaleString()}`
                  : `${activeSlice.value}%`}
              </span>
              <span className="mt-0.5 text-[10px] text-text-muted">{activeSlice.value}%</span>
            </>
          ) : (
            <>
              <span className="max-w-[92px] text-center font-mono text-sm font-bold tabular-nums leading-tight text-text-primary">
                {centerValue}
              </span>
              {centerLabel && <span className="text-[10px] text-text-muted">{t(centerLabel)}</span>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
