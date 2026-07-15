import {
  Area,
  AreaChart,
  Bar,
  ComposedChart,
  Line,
  LineChart,
  Cell,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { type Candle, fmtNum, sma } from "@/lib/data";
import { useTheme } from "@/hooks/use-theme";
import { useLang } from "@/hooks/use-lang";
import { useId } from "react";

/** Theme-aware chart colors. Dark values are unchanged from the original design. */
export function useChartTheme() {
  const { theme } = useTheme();
  const light = theme === "light";
  return {
    light,
    grid: light ? "#e6eaf2" : "#1a2535",
    tick: "#64748b",
    teal: light ? "#0d9488" : "#00d4aa",
    expense: light ? "#c4615a" : "#e5484d",
    benchmark: light ? "#64748b" : "#94a3b8",
    cursorBar: light ? "rgba(15,23,42,0.05)" : "#1f2d40",
    tooltip: {
      background: light ? "#ffffff" : "#1a2332",
      border: light ? "1px solid rgba(15,23,42,0.10)" : "1px solid #2a3a50",
      borderRadius: 10,
      fontSize: 12,
      color: light ? "#0f172a" : "#e2e8f0",
      boxShadow: light
        ? "0 10px 28px rgba(15,23,42,0.14)"
        : "0 8px 24px rgba(0,0,0,0.5)",
    },
    tooltipLabel: light ? "#475569" : "#94a3b8",
  };
}

/** Harmonious, desaturated donut palette for white cards in light mode. */
export const DONUT_LIGHT_PALETTE = ["#0d8a7e", "#5b7aa6", "#c08a4a", "#9b7aa6", "#94a3b8"];

/** Remap neon dark-theme hexes to deeper, desaturated light-theme equivalents. */
const LIGHT_SPARK: Record<string, string> = {
  "#00d4aa": "#0d9488",
  "#e5484d": "#c4615a",
};

export function Sparkline({ data, color }: { data: number[]; color: string }) {
  const { theme } = useTheme();
  const stroke = theme === "light" ? (LIGHT_SPARK[color.toLowerCase()] ?? color) : color;
  const d = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={36}>
      <LineChart data={d} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
        <Line type="monotone" dataKey="v" stroke={stroke} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

interface CandleShapeProps {
  x?: number;
  width?: number;
  y?: number;
  height?: number;
  payload?: Candle;
}

const CandleShape = (props: CandleShapeProps) => {
  const { x = 0, width = 0, y, height, payload } = props;
  if (y == null || height == null || !payload) return null;
  const { open, close, high, low } = payload;
  const up = close >= open;
  const color = up ? "#00d4aa" : "#e5484d";
  const span = high - low || 1;
  const ratio = height / span;
  const yOpen = y + (high - open) * ratio;
  const yClose = y + (high - close) * ratio;
  const bodyTop = Math.min(yOpen, yClose);
  const bodyH = Math.max(Math.abs(yClose - yOpen), 1);
  const cx = x + width / 2;
  return (
    <g>
      <line x1={cx} y1={y} x2={cx} y2={y + height} stroke={color} strokeWidth={1} />
      <rect
        x={x + width * 0.18}
        y={bodyTop}
        width={width * 0.64}
        height={bodyH}
        fill={color}
        rx={1}
      />
    </g>
  );
};

function OHLCTooltip({ active, payload }: { active?: boolean; payload?: { payload?: Candle }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0]?.payload as Candle;
  if (!p) return null;
  const up = p.close >= p.open;
  const chg = p.close - p.open;
  return (
    <div className="rounded-[8px] border border-border-hover bg-elevated p-3 text-xs shadow-[0_4px_24px_rgba(0,0,0,0.6)]">
      <div className="mb-1 font-medium text-text-secondary">{p.date}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono tabular-nums text-text-primary">
        <span className="text-text-muted">O</span>
        <span>{fmtNum(p.open)}</span>
        <span className="text-text-muted">H</span>
        <span>{fmtNum(p.high)}</span>
        <span className="text-text-muted">L</span>
        <span>{fmtNum(p.low)}</span>
        <span className="text-text-muted">C</span>
        <span>{fmtNum(p.close)}</span>
        <span className="text-text-muted">Vol</span>
        <span>{p.volume}M</span>
      </div>
      <div className={`mt-1 font-mono text-xs ${up ? "text-bull" : "text-bear"}`}>
        {up ? "+" : ""}
        {fmtNum(chg)} ({((chg / p.open) * 100).toFixed(2)}%)
      </div>
    </div>
  );
}

export function CandlestickChart({
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
  const ma20 = maSeries?.ma20 ?? sma(data, 20);
  const ma50 = maSeries?.ma50 ?? sma(data, 50);
  const ma100 = maSeries?.ma100 ?? sma(data, 100);
  const ma200 = maSeries?.ma200 ?? sma(data, 200);
  const enriched = data.map((c, i) => ({
    ...c,
    range: [c.low, c.high] as [number, number],
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
        <Tooltip content={<OHLCTooltip />} cursor={{ stroke: ct.benchmark, strokeDasharray: "4 4" }} />
        <Bar yAxisId="vol" dataKey="volume" isAnimationActive={false}>
          {enriched.map((c, i) => (
            <Cell key={i} fill={c.close >= c.open ? "#00d4aa" : "#e5484d"} fillOpacity={0.35} />
          ))}
        </Bar>
        <Bar yAxisId="price" dataKey="range" shape={<CandleShape />} isAnimationActive={false} />
        {mas.includes("MA20") && (
          <Line
            yAxisId="price"
            dataKey="ma20"
            stroke="#f59e0b"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {mas.includes("MA50") && (
          <Line
            yAxisId="price"
            dataKey="ma50"
            stroke="#3b82f6"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {mas.includes("MA100") && (
          <Line
            yAxisId="price"
            dataKey="ma100"
            stroke="#ef4444"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {mas.includes("MA200") && (
          <Line
            yAxisId="price"
            dataKey="ma200"
            stroke="#8b5cf6"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {currentPrice !== undefined && (
          <ReferenceLine
            y={currentPrice}
            stroke="#00d4aa"
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: `PKR ${currentPrice.toFixed(2)}`,
              position: "right",
              fill: "#00d4aa",
              fontSize: 10,
            }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

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
          <Line
            yAxisId="price"
            dataKey="ma20"
            name="MA20"
            stroke="#f59e0b"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {mas.includes("MA50") && (
          <Line
            yAxisId="price"
            dataKey="ma50"
            name="MA50"
            stroke="#3b82f6"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {mas.includes("MA100") && (
          <Line
            yAxisId="price"
            dataKey="ma100"
            name="MA100"
            stroke="#ef4444"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {mas.includes("MA200") && (
          <Line
            yAxisId="price"
            dataKey="ma200"
            name="MA200"
            stroke="#8b5cf6"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
          />
        )}
        {currentPrice !== undefined && (
          <ReferenceLine
            y={currentPrice}
            stroke="#00d4aa"
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: `PKR ${currentPrice.toFixed(2)}`,
              position: "right",
              fill: "#00d4aa",
              fontSize: 10,
            }}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}


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
        <Tooltip
          contentStyle={ct.tooltip}
          labelStyle={{ color: ct.tooltipLabel }}
        />
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
