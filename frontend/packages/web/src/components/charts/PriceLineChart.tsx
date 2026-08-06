import { useCallback, useId, useMemo, useRef, useState } from "react";
import {
  Area,
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
import { useLang } from "@/hooks/use-lang";
import { useChartTheme } from "@/components/charts/chart-theme";
import { ChartReadout } from "@/components/charts/ChartReadout";
import {
  formatAxisTick,
  pickTickValues,
  priceDecimals,
  resolveScale,
  scaleForTicks,
} from "@/components/charts/chart-format";

export function PriceLineChart({
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
  const priceLineGradientId = useId();

  const [zoom, setZoom] = useState<{ from: number; to: number } | null>(null);
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const [hovered, setHovered] = useState<Candle | null>(null);

  const fingerprint = `${data.length ? data[0].t : 0}:${tf}`;
  const lastFingerprint = useRef(fingerprint);
  if (lastFingerprint.current !== fingerprint) {
    lastFingerprint.current = fingerprint;
    if (zoom) setZoom(null);
  }

  const enriched = useMemo(() => {
    const ma20 = maSeries?.ma20 ?? sma(data, 20);
    const ma50 = maSeries?.ma50 ?? sma(data, 50);
    const ma100 = maSeries?.ma100 ?? sma(data, 100);
    const ma200 = maSeries?.ma200 ?? sma(data, 200);
    return data.map((c, i) => ({
      ...c,
      ma20: ma20[i] ?? null,
      ma50: ma50[i] ?? null,
      ma100: ma100[i] ?? null,
      ma200: ma200[i] ?? null,
    }));
  }, [data, maSeries]);

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
    // dir="ltr" — see CandlestickChart: a time axis reads left-to-right in
    // every locale, including the Urdu (RTL) side of the app.
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
          margin={{ top: 22, right: 8, left: 0, bottom: 0 }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={() => {
            setHovered(null);
            setDrag(null);
          }}
        >
          <defs>
            <linearGradient id={priceLineGradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={ct.teal} stopOpacity={ct.light ? 0.18 : 0.32} />
              <stop offset="100%" stopColor={ct.teal} stopOpacity={0} />
            </linearGradient>
          </defs>
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
            tickFormatter={(v) => formatNumber(Number(v), dp)}
          />
          <YAxis yAxisId="vol" domain={[0, maxVol > 0 ? maxVol * 5 : 1]} hide />
          <Tooltip
            content={() => null}
            cursor={{ stroke: ct.benchmark, strokeDasharray: "4 4" }}
            isAnimationActive={false}
          />
          <Bar yAxisId="vol" dataKey="volume" isAnimationActive={false}>
            {visible.map((c, i) => (
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
              connectNulls
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
              connectNulls
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
              connectNulls
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
