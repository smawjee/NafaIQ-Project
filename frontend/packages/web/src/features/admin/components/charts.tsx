/**
 * Chart wrappers.
 *
 * Recharts is already a project dependency; these wrappers exist so every chart
 * in the console shares one grid style, one tooltip, one palette and one empty
 * state. Series are distinguished by label *and* hue, never hue alone.
 */
import { type ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";
import { EmptyBlock } from "./states";

/**
 * Categorical palette. Emerald leads (brand), then hues chosen to stay
 * distinguishable under the common forms of colour-vision deficiency.
 */
export const CHART_COLORS = [
  "var(--color-primary)",
  "#38bdf8",
  "#f5a524",
  "#a78bfa",
  "#f2555a",
  "#64748b",
] as const;

const AXIS_PROPS = {
  stroke: "var(--color-text-muted)",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

/** Shared tooltip surface — matches popovers rather than Recharts' default. */
function ChartTooltip({
  active,
  payload,
  label,
  valueFormatter,
}: {
  active?: boolean;
  payload?: { name?: string; value?: number; color?: string; payload?: Record<string, unknown> }[];
  label?: string | number;
  valueFormatter?: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-2.5 py-2 shadow-[var(--admin-elev-3)]">
      {label != null && (
        <div className="mb-1 text-[11px] font-medium text-text-secondary">{String(label)}</div>
      )}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: p.color }}
            aria-hidden
          />
          <span className="text-text-muted">{p.name}</span>
          <span className="tabular ms-auto font-medium text-text-primary">
            {valueFormatter && typeof p.value === "number"
              ? valueFormatter(p.value)
              : (p.value ?? "—").toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

function ChartFrame({
  height = 220,
  isEmpty,
  emptyLabel,
  children,
  className,
}: {
  height?: number;
  isEmpty: boolean;
  emptyLabel?: string;
  children: ReactNode;
  className?: string;
}) {
  if (isEmpty) {
    return (
      <div style={{ height }} className="flex items-center justify-center">
        <EmptyBlock label={emptyLabel ?? "No data for this period"} />
      </div>
    );
  }
  // A fixed height wrapper reserves layout space before Recharts measures,
  // which keeps CLS at zero.
  return (
    <div style={{ height }} className={cn("w-full", className)}>
      <ResponsiveContainer width="100%" height="100%">
        {children as React.ReactElement}
      </ResponsiveContainer>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export interface SeriesPoint {
  label: string;
  value: number;
}

/** Trend area chart — used for time series. */
export function TrendChart({
  data,
  name = "Value",
  height = 220,
  valueFormatter,
}: {
  data: SeriesPoint[];
  name?: string;
  height?: number;
  valueFormatter?: (v: number) => string;
}) {
  return (
    <ChartFrame height={height} isEmpty={data.length === 0}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="admin-trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.28} />
            <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="label" {...AXIS_PROPS} />
        <YAxis {...AXIS_PROPS} width={48} />
        <Tooltip
          cursor={{ stroke: "var(--color-border-hover)" }}
          content={<ChartTooltip valueFormatter={valueFormatter} />}
        />
        <Area
          type="monotone"
          dataKey="value"
          name={name}
          stroke="var(--color-primary)"
          strokeWidth={2}
          fill="url(#admin-trend-fill)"
          dot={false}
          activeDot={{ r: 3.5 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ChartFrame>
  );
}

/** Horizontal-comparison bar chart — used for categorical volumes. */
export function CategoryBarChart({
  data,
  name = "Count",
  height = 220,
  valueFormatter,
}: {
  data: SeriesPoint[];
  name?: string;
  height?: number;
  valueFormatter?: (v: number) => string;
}) {
  return (
    <ChartFrame height={height} isEmpty={data.length === 0}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="label" {...AXIS_PROPS} interval={0} />
        <YAxis {...AXIS_PROPS} width={48} />
        <Tooltip
          cursor={{ fill: "var(--color-hover)" }}
          content={<ChartTooltip valueFormatter={valueFormatter} />}
        />
        <Bar dataKey="value" name={name} radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}

/**
 * Donut with an always-visible legend. The legend carries the label and the
 * value, so the chart is still readable without colour perception.
 */
export function DonutChart({
  data,
  height = 200,
  centerLabel,
}: {
  data: SeriesPoint[];
  height?: number;
  centerLabel?: string;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="relative shrink-0" style={{ width: height, height }}>
        <ChartFrame height={height} isEmpty={total === 0}>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={2}
              stroke="none"
              isAnimationActive={false}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip />} />
          </PieChart>
        </ChartFrame>
        {total > 0 && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="tabular text-xl font-semibold text-text-primary">
              {total.toLocaleString()}
            </span>
            {centerLabel && <span className="text-[10px] text-text-muted">{centerLabel}</span>}
          </div>
        )}
      </div>

      {total > 0 && (
        <ul className="min-w-0 flex-1 space-y-1.5">
          {data.map((d, i) => (
            <li key={d.label} className="flex items-center gap-2 text-sm">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-text-secondary">{d.label}</span>
              <span className="tabular font-medium text-text-primary">
                {d.value.toLocaleString()}
              </span>
              <span className="tabular w-11 text-end text-xs text-text-muted">
                {((d.value / total) * 100).toFixed(0)}%
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Inline sparkline for KPI tiles. Decorative — always paired with a figure. */
export function Sparkline({ data, className }: { data: number[]; className?: string }) {
  if (data.length < 2) return null;
  const points = data.map((value, i) => ({ label: String(i), value }));
  return (
    <div className={cn("h-8 w-full", className)} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--color-primary)"
            strokeWidth={1.5}
            fill="var(--color-primary)"
            fillOpacity={0.12}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
