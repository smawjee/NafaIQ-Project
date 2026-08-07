import { useCallback, useMemo, useRef, useState } from "react";
import {
  Bar,
  Cell,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type Candle, sma } from "@/lib/data";
import { formatNumber } from "@/lib/format";
import { useChartTheme } from "@/components/charts/chart-theme";
import { ChartReadout } from "@/components/charts/ChartReadout";
import {
  MIN_CANDLE_BODY_PX,
  formatAxisTick,
  priceDecimals,
  pickTickValues,
  resolveScale,
  scaleForTicks,
} from "@/components/charts/chart-format";
import { useLang } from "@/hooks/use-lang";

const BULL = "#00d4aa";
const BEAR = "#e5484d";

interface EnrichedCandle extends Candle {
  range: [number, number];
  ma20: number | null;
  ma50: number | null;
  ma100: number | null;
  ma200: number | null;
}

interface CandleShapeProps {
  x?: number;
  width?: number;
  y?: number;
  height?: number;
  payload?: Candle;
}

/**
 * One candle.
 *
 * Recharts hands this the bounding box of the low–high band (the `range`
 * datum), so open/close are positioned by interpolating inside it rather than
 * by a second scale.
 */
const CandleShape = (props: CandleShapeProps) => {
  const { x = 0, width = 0, y, height, payload } = props;
  if (y == null || height == null || !payload) return null;
  const { open, close, high, low } = payload;
  const up = close >= open;
  const color = up ? BULL : BEAR;
  const span = high - low || 1;
  const ratio = height / span;
  const yOpen = y + (high - open) * ratio;
  const yClose = y + (high - close) * ratio;
  const bodyTop = Math.min(yOpen, yClose);
  const bodyH = Math.max(Math.abs(yClose - yOpen), 1);
  const cx = x + width / 2;

  // Below ~3px a body and its wick render as one indistinguishable smear, and
  // 400 intraday bars in a 900px pane is well under that. Collapsing to a
  // single hairline per bar keeps the shape of the series readable instead of
  // turning it into a solid block.
  if (width < MIN_CANDLE_BODY_PX) {
    return <line x1={cx} y1={y} x2={cx} y2={y + height} stroke={color} strokeWidth={1} />;
  }

  const bodyW = Math.max(width * 0.64, 1);
  return (
    <g>
      <line x1={cx} y1={y} x2={cx} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={cx - bodyW / 2} y={bodyTop} width={bodyW} height={bodyH} fill={color} rx={1} />
    </g>
  );
};

export function CandlestickChart({
  data,
  height = 480,
  mas = ["MA20", "MA50", "MA100"],
  maSeries,
  currentPrice,
  tf = "6M",
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
  /** Drives tick granularity and the readout's date format. */
  tf?: string;
}) {
  const ct = useChartTheme();
  const { t } = useLang();

  // Drag-to-zoom. `zoom` is the committed window; `drag` is the selection in
  // progress. Both are timestamps so they survive a data refresh (a live tick
  // appends a bar and would invalidate index-based bounds).
  const [zoom, setZoom] = useState<{ from: number; to: number } | null>(null);
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const [hovered, setHovered] = useState<Candle | null>(null);

  // Reset the zoom whenever the underlying series changes identity (symbol or
  // timeframe switch). Keyed on a cheap fingerprint rather than the array so a
  // live tick appending one bar does not throw away the reader's zoom.
  const fingerprint = `${data.length ? data[0].t : 0}:${tf}`;
  const lastFingerprint = useRef(fingerprint);
  if (lastFingerprint.current !== fingerprint) {
    lastFingerprint.current = fingerprint;
    if (zoom) setZoom(null);
  }

  const enriched = useMemo<EnrichedCandle[]>(() => {
    const ma20 = maSeries?.ma20 ?? sma(data, 20);
    const ma50 = maSeries?.ma50 ?? sma(data, 50);
    const ma100 = maSeries?.ma100 ?? sma(data, 100);
    const ma200 = maSeries?.ma200 ?? sma(data, 200);
    return data.map((c, i) => ({
      ...c,
      range: [c.low, c.high] as [number, number],
      ma20: ma20[i] ?? null,
      ma50: ma50[i] ?? null,
      ma100: ma100[i] ?? null,
      ma200: ma200[i] ?? null,
    }));
  }, [data, maSeries]);

  // Filter AFTER the MAs are merged in, so a zoomed view keeps averages that
  // were computed over the full warmup rather than recomputing them from the
  // visible slice (which would blank MA200 on any window under 200 bars).
  const visible = useMemo(() => {
    if (!zoom) return enriched;
    const slice = enriched.filter((d) => d.t >= zoom.from && d.t <= zoom.to);
    return slice.length >= 2 ? slice : enriched;
  }, [enriched, zoom]);

  const onMouseDown = useCallback((e: { activeLabel?: string | number } | null) => {
    const at = Number(e?.activeLabel);
    if (Number.isFinite(at)) setDrag({ from: at, to: at });
  }, []);

  const onMouseMove = useCallback(
    (e: { activeLabel?: string | number; activePayload?: { payload?: Candle }[] } | null) => {
      setHovered(e?.activePayload?.[0]?.payload ?? null);
      const at = Number(e?.activeLabel);
      if (Number.isFinite(at)) setDrag((d) => (d ? { ...d, to: at } : d));
    },
    [],
  );

  const onMouseUp = useCallback(() => {
    setDrag((d) => {
      if (d && d.from !== d.to) {
        setZoom({ from: Math.min(d.from, d.to), to: Math.max(d.from, d.to) });
      }
      return null;
    });
  }, []);

  if (!data || data.length === 0) {
    return (
      <div
        className="flex h-full w-full items-center justify-center text-xs text-text-muted"
        style={{ height: height >= 9999 ? "100%" : height }}
      >
        {t("No price data for this range")}
      </div>
    );
  }

  const maxVol = Math.max(0, ...visible.map((d) => d.volume));
  const lows = Math.min(...visible.map((d) => d.low));
  const highs = Math.max(...visible.map((d) => d.high));
  // A flat series (one bar, or a suspended stock) has zero span — pad by a
  // fraction of the price so the candle lands mid-pane instead of on the axis.
  const span = highs - lows;
  const pad = span > 0 ? span * 0.08 : Math.abs(highs) * 0.02 || 1;
  const dp = priceDecimals(span);
  // Derived from the bars on screen, not from `tf`: 1D/1W fall back to
  // daily candles when there is no intraday data, and labelling those with
  // the clock formatter rendered every tick as "05:00".
  const scale = resolveScale(tf, visible);
  // Ticks are chosen here, not by minTickGap, so the label format can be
  // validated against them: a 6M window put two ticks in each month and the
  // axis read "Mar 26, Mar 26, Apr 26, Apr 26".
  const tickValues = pickTickValues(visible);
  const tickScale = scaleForTicks(scale, tickValues);

  return (
    // dir="ltr": time runs left-to-right on a financial chart in every locale,
    // and Recharts positions its SVG from the container's writing direction —
    // without this the axis mirrors on the Urdu (RTL) side of the app.
    <div className="relative h-full w-full" dir="ltr">
      <ChartReadout bar={hovered ?? visible[visible.length - 1]} scale={scale} decimals={dp} />
      {zoom && (
        <button
          type="button"
          onClick={() => setZoom(null)}
          dir="auto"
          className="absolute end-2 top-1 z-10 rounded-[6px] border border-border bg-elevated px-2 py-0.5 text-[10px] font-medium text-text-secondary hover:text-text-primary"
        >
          {t("Reset zoom")}
        </button>
      )}
      <ResponsiveContainer width="100%" height={height >= 9999 ? "100%" : height}>
        <ComposedChart
          data={visible}
          // Volume and price are the SAME column on a financial chart, not two
          // neighbours. Recharts groups multiple <Bar> series side by side by
          // default and splits the category band between them, which left the
          // candle 5px of a 19.5px slot (measured) — a third of its width, and
          // under MIN_CANDLE_BODY_PX on any denser window, which is why every
          // bar collapsed to a hairline. A -100% gap overlays them so the
          // candle gets the whole band (17px on the same data).
          barGap="-100%"
          margin={{ top: 22, right: 8, left: 0, bottom: 0 }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={() => {
            setHovered(null);
            setDrag(null);
          }}
        >
          <CartesianGrid stroke={ct.grid} vertical={false} />
          <XAxis
            dataKey="t"
            ticks={tickValues}
            tick={{ fill: ct.tick, fontSize: 10 }}
            minTickGap={24}
            axisLine={{ stroke: ct.grid }}
            tickLine={false}
            tickFormatter={(v) => formatAxisTick(Number(v), tickScale)}
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={[lows - pad, highs + pad]}
            tick={{ fill: ct.tick, fontSize: 10 }}
            width={64}
            axisLine={false}
            tickLine={false}
            // Precision follows the visible range. The old fixed `fmtNum(v, 0)`
            // rendered every tick of a PKR 2.38 stock as "2".
            tickFormatter={(v) => formatNumber(Number(v), dp)}
          />
          {/* Volume occupies the bottom fifth of the pane. The x5 headroom is
              what keeps it there; guard the empty case so a series with no
              volume does not collapse the domain to [0, 0]. */}
          <YAxis yAxisId="vol" domain={[0, maxVol > 0 ? maxVol * 5 : 1]} hide />
          <Tooltip
            content={() => null}
            cursor={{ stroke: ct.benchmark, strokeDasharray: "4 4" }}
            isAnimationActive={false}
          />
          <Bar yAxisId="vol" dataKey="volume" isAnimationActive={false}>
            {visible.map((c, i) => (
              <Cell key={i} fill={c.close >= c.open ? BULL : BEAR} fillOpacity={0.35} />
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
              connectNulls
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
              connectNulls
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
              connectNulls
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
              connectNulls
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
                value: formatNumber(currentPrice, dp),
                position: "right",
                fill: ct.teal,
                fontSize: 10,
              }}
            />
          )}
          {drag && drag.from !== drag.to && (
            <ReferenceArea
              yAxisId="price"
              x1={drag.from}
              x2={drag.to}
              fill={ct.benchmark}
              fillOpacity={0.12}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
