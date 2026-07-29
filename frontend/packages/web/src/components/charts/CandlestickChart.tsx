import {
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
import { useChartTheme } from "@/components/charts/chart-theme";

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
  maSeries?: {
    ma20: (number | null)[];
    ma50: (number | null)[];
    ma100: (number | null)[];
    ma200: (number | null)[];
  };
  currentPrice?: number;
}) {
  const ct = useChartTheme();
  // Defensive: a transient empty `data` (during a symbol change) used to
  // feed -Infinity / +Infinity into YAxis `domain` and crash Recharts. The
  // parent (PSX / StockDetail) now keys the chart by `sym` so this should
  // not happen in practice, but guard against it anyway.
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
        <Tooltip
          content={<OHLCTooltip />}
          cursor={{ stroke: ct.benchmark, strokeDasharray: "4 4" }}
        />
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
            yAxisId="price"
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
