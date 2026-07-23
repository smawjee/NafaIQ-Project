// PSX Market Terminal (`/psx`): index cards, price chart with candle/line toggle
// + symbol/timeframe/MA controls, AI bar, screener (signal filters), sector
// heatmap. Single FlatList for virtualization. Theme + i18n aware.
// Live data via React Query hooks (src/hooks/queries/use-market.ts) — mirrors
// the web app's src/features/psx/PSX.tsx wiring.
import { useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { PriceLineChart } from "@/components/charts/PriceLineChart";
import { Sparkline } from "@/components/charts/Sparkline";
import { AiReportSheet } from "@/components/ai/AiReportSheet";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { SectorHeatmap } from "@/components/psx/SectorHeatmap";
import { SignalBadge, Text } from "@/components/ui";
import { Chip, ChipRow, Segmented } from "@/components/ui/controls";
import { fonts } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import {
  useIndexCards,
  useMarketMovers,
  usePsxBatchSignals,
  usePsxHistory,
  usePsxIndexData,
  usePsxLiveMarket,
  usePsxRealtime,
  usePsxScreenerMetrics,
  usePsxSignal,
  usePsxSymbols,
  usePsxTreemap,
  useUnusualActivity,
  type ApiUnusualActivity,
  type UiTicker,
} from "@/hooks/queries/use-market";
import { useMarketBrief } from "@/hooks/ai/use-market-brief";
import { useTheme } from "@/hooks/use-theme";
import { Activity, ChevronRight, Sparkles } from "@/lib/icons";
import { fmtNum, type Signal } from "@nafaiq/shared";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

const TIMEFRAMES: Record<string, number> = { "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 260 };
const SIGNALS: (Signal | "All")[] = ["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"];

// Benchmark index display-name → backend code (for GET /api/index/{code}).
// useIndexCards() drops the code, so we re-derive it here for the sparkline.
const INDEX_CODE_BY_NAME: Record<string, string> = {
  "KSE-100": "KSE100",
  "KSE-30": "KSE30",
  "KMI-30": "KMI30",
  "KSE All Share": "ALLSHR",
};
const MOVER_TABS = ["Gainers", "Losers", "Most Active"] as const;

interface ScreenerRow {
  ticker: string;
  sector: string;
  price: number | null;
  changePct: number | null;
  signal: Signal | null;
  rsi: number | null;
}

export default function PsxScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const { t } = useLang();
  const { width } = useWindowDimensions();
  const chartW = width - 64;

  const [sym, setSym] = useState("HBL");
  const [tf, setTf] = useState("3M");
  const [chartType, setChartType] = useState("Candle");
  const [ma20, setMa20] = useState(true);
  const [ma50, setMa50] = useState(false);
  const [signal, setSignal] = useState<Signal | "All">("All");
  const [selectedIdx, setSelectedIdx] = useState("KSE-100");
  const [moverTab, setMoverTab] = useState<(typeof MOVER_TABS)[number]>("Gainers");

  usePsxRealtime();
  const { data: snapshot, isPending: snapshotPending, isError: snapshotError } = usePsxLiveMarket();
  const { data: symbolsData } = usePsxSymbols();
  const { data: batchSignals } = usePsxBatchSignals(50);
  const { data: screenerMetrics } = usePsxScreenerMetrics();
  const { data: candles, isPending: candlesPending, isError: candlesError } = usePsxHistory(
    sym,
    TIMEFRAMES[tf],
  );
  const { data: aiSignal } = usePsxSignal(sym);
  const brief = useMarketBrief();
  const indexCards = useIndexCards();

  // Real EOD series for the selected index card — replaces the flat
  // placeholder sparkline (GET /api/index/{code}).
  const selectedCode = INDEX_CODE_BY_NAME[selectedIdx];
  const { data: indexSeries } = usePsxIndexData(selectedCode);
  const selectedSpark = useMemo(
    () =>
      (indexSeries ?? [])
        .map((b) => b.close)
        .filter((v): v is number => typeof v === "number" && Number.isFinite(v))
        .slice(-40),
    [indexSeries],
  );

  // Movers tabs (Gainers / Losers / Most Active) off the live snapshot.
  const moverSort = moverTab === "Gainers" ? "gainers" : moverTab === "Losers" ? "losers" : "volume";
  const movers = useMarketMovers(moverSort, 12);

  const { data: treemap, isPending: treemapPending, isError: treemapError } = usePsxTreemap();

  const {
    data: unusual,
    isPending: unusualPending,
    isError: unusualError,
  } = useUnusualActivity(20);

  const nameMap = useMemo(
    () => new Map((symbolsData ?? []).map((s) => [s.symbol, s.name])),
    [symbolsData],
  );

  // Symbol chips: most-active tickers from the live snapshot (top 12 by
  // volume), always including the current selection.
  const symbolChips = useMemo(() => {
    const top = (snapshot ?? [])
      .slice()
      .sort((a, b) => (b.volume ?? 0) - (a.volume ?? 0))
      .slice(0, 12)
      .map((s) => s.symbol);
    return top.includes(sym) ? top : [sym, ...top];
  }, [snapshot, sym]);

  const mas = useMemo(
    () =>
      [ma20 ? { period: 20, color: colors.warning } : null, ma50 ? { period: 50, color: colors.info } : null].filter(
        Boolean,
      ) as { period: number; color: string }[],
    [ma20, ma50, colors],
  );

  // Screener universe: live snapshot joined with sector names, model signals
  // and RSI (same joins as the web screener; no fabricated values).
  const rows = useMemo<ScreenerRow[]>(() => {
    if (!snapshot) return [];
    const sectorMap = new Map((symbolsData ?? []).map((s) => [s.symbol, s.sector ?? "—"]));
    const signalMap = new Map<string, Signal>();
    for (const s of batchSignals?.signals ?? []) {
      if (s.signal) signalMap.set(s.symbol, s.signal);
    }
    const metricsMap = new Map((screenerMetrics ?? []).map((m) => [m.symbol, m.rsi]));
    const all = snapshot.map<ScreenerRow>((s) => ({
      ticker: s.symbol,
      sector: sectorMap.get(s.symbol) ?? "—",
      price: s.price,
      changePct: s.change_pct,
      signal: signalMap.get(s.symbol) ?? null,
      rsi: metricsMap.get(s.symbol) ?? null,
    }));
    return signal === "All" ? all : all.filter((r) => r.signal === signal);
  }, [snapshot, symbolsData, batchSignals, screenerMetrics, signal]);

  const modelReady = !!aiSignal && aiSignal.signal !== "NO SIGNAL";

  const renderRow = useCallback(
    ({ item }: { item: ScreenerRow }) => {
      const pct = item.changePct;
      return (
        <Pressable
          style={[styles.row, { borderBottomColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel={`${item.ticker}${item.signal ? `, ${item.signal}` : ""}${item.rsi != null ? `, RSI ${Math.round(item.rsi)}` : ""}`}
          onPress={() => router.push(`/stock/${item.ticker}`)}
        >
          <View style={{ flex: 1 }}>
            <Text style={styles.ticker}>{item.ticker}</Text>
            <Text variant="muted">{item.sector}</Text>
          </View>
          <View style={styles.priceCol}>
            <Text variant="mono" style={{ fontSize: 13.5 }}>
              {item.price != null ? fmtNum(item.price) : "—"}
            </Text>
            <Text
              style={{
                fontSize: 12,
                marginTop: 2,
                fontFamily: fonts.mono,
                color: pct == null ? colors.textMuted : pct >= 0 ? colors.bull : colors.bear,
              }}
            >
              {pct == null ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`}
            </Text>
          </View>
          <View style={styles.sigCol}>
            {item.signal ? <SignalBadge signal={item.signal} /> : <Text variant="muted">—</Text>}
          </View>
        </Pressable>
      );
    },
    [router, colors],
  );

  const renderMover = useCallback(
    ({ item }: { item: UiTicker }) => {
      const up = item.changePct >= 0;
      return (
        <Pressable
          onPress={() => router.push(`/stock/${item.symbol}`)}
          accessibilityRole="button"
          accessibilityLabel={`${item.symbol}, ${fmtNum(item.price)}, ${up ? "up" : "down"} ${Math.abs(item.changePct).toFixed(2)} percent`}
        >
          <GlassCard radius={14} intensity={16} style={styles.moverCard}>
            <Text style={styles.ticker} numberOfLines={1}>{item.symbol}</Text>
            <Text variant="mono" style={{ fontSize: 13.5, marginTop: 2 }}>
              {item.price != null ? fmtNum(item.price) : "—"}
            </Text>
            <Text style={{ fontSize: 12, marginTop: 2, fontFamily: fonts.mono, color: up ? colors.bull : colors.bear }}>
              {up ? "+" : ""}
              {item.changePct.toFixed(2)}%
            </Text>
            <Text variant="muted" style={{ fontSize: 10.5, marginTop: 2 }} numberOfLines={1}>
              {t("Vol")} {fmtNum(item.volume)}
            </Text>
          </GlassCard>
        </Pressable>
      );
    },
    [router, colors, t],
  );

  const renderUnusual = useCallback(
    ({ item }: { item: ApiUnusualActivity }) => {
      const pct = item.change_pct ?? 0;
      const up = pct >= 0;
      return (
        <Pressable
          onPress={() => router.push(`/stock/${item.symbol}`)}
          accessibilityRole="button"
          accessibilityLabel={`${item.symbol}, ${up ? "up" : "down"} ${Math.abs(pct).toFixed(2)} percent${item.volume_ratio != null ? `, ${item.volume_ratio.toFixed(1)} times average volume` : ""}`}
        >
          <GlassCard radius={14} intensity={16} style={styles.unusualCard}>
            <View style={styles.between}>
              <Text style={styles.ticker} numberOfLines={1}>{item.symbol}</Text>
              <Text style={{ fontSize: 12.5, fontFamily: fonts.mono, color: up ? colors.bull : colors.bear }}>
                {up ? "+" : ""}
                {pct.toFixed(2)}%
              </Text>
            </View>
            {item.volume_ratio != null && (
              <Text style={{ fontSize: 11, color: colors.warning, marginTop: 4, fontFamily: fonts.mono }}>
                {item.volume_ratio.toFixed(1)}× {t("avg vol")}
              </Text>
            )}
            {item.reason ? (
              <Text variant="muted" style={{ fontSize: 10.5, marginTop: 4 }} numberOfLines={2}>
                {item.reason}
              </Text>
            ) : null}
          </GlassCard>
        </Pressable>
      );
    },
    [router, colors, t],
  );

  const header = (
    <View style={{ gap: 16 }}>
      <Text variant="display" style={{ fontFamily: AVENIR }}>{t("PSX Market")}</Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
        {indexCards.map((idx) => {
          const isSel = idx.name === selectedIdx;
          // Real EOD closes for the selected card; a flat line otherwise.
          const spark = isSel && selectedSpark.length >= 2 ? selectedSpark : new Array(7).fill(idx.value);
          return (
            <Pressable
              key={idx.name}
              onPress={() => setSelectedIdx(idx.name)}
              accessibilityRole="button"
              accessibilityState={{ selected: isSel }}
              accessibilityLabel={`${idx.name}, ${idx.value > 0 ? idx.value.toLocaleString() : "no data"}, ${idx.changePct >= 0 ? "up" : "down"} ${Math.abs(idx.changePct).toFixed(2)} percent`}
            >
              <GlassCard
                radius={16}
                intensity={18}
                style={[styles.indexCard, isSel && { borderColor: colors.primary + "88", borderWidth: 1 }]}
              >
                <Text variant="muted">{idx.name}</Text>
                <Text variant="mono" style={{ fontSize: 16, marginVertical: 2 }}>
                  {idx.value > 0 ? idx.value.toLocaleString() : "—"}
                </Text>
                <Text style={{ color: idx.changePct >= 0 ? colors.bull : colors.bear, fontSize: 12 }}>
                  {idx.changePct >= 0 ? "▲" : "▼"} {Math.abs(idx.changePct).toFixed(2)}%
                </Text>
                <Sparkline data={spark} width={120} height={28} />
              </GlassCard>
            </Pressable>
          );
        })}
      </ScrollView>

      <GlassCard style={styles.chartCard}>
        <View style={styles.between}>
          <View>
            <Text variant="title">{sym}</Text>
            <Text variant="muted">{nameMap.get(sym) ?? t("Pakistan Stock Exchange")}</Text>
          </View>
          {modelReady ? (
            <SignalBadge signal={aiSignal!.signal} />
          ) : (
            <Text variant="muted">{t("Signal unavailable")}</Text>
          )}
        </View>
        <ChipRow options={symbolChips} value={sym} onChange={setSym} />
        <Segmented options={Object.keys(TIMEFRAMES)} value={tf} onChange={setTf} />
        <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
          <View style={{ flex: 1 }}>
            <Segmented options={["Candle", "Line"]} value={chartType} onChange={setChartType} />
          </View>
          <Chip label="MA20" active={ma20} onPress={() => setMa20((v) => !v)} color={colors.warning} />
          <Chip label="MA50" active={ma50} onPress={() => setMa50((v) => !v)} color={colors.info} />
        </View>
        {candlesPending ? (
          <View style={styles.chartPlaceholder} accessibilityLabel={t("Loading chart data")}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : candlesError || !candles || candles.length === 0 ? (
          <View style={styles.chartPlaceholder}>
            <Text variant="muted">
              {candlesError ? t("Could not load chart data.") : t("No chart data available.")}
            </Text>
          </View>
        ) : chartType === "Candle" ? (
          <CandlestickChart data={candles} width={chartW} mas={mas} />
        ) : (
          <PriceLineChart data={candles} width={chartW} mas={mas} />
        )}
        <View style={[styles.aiBar, { backgroundColor: colors.ai + "12", borderColor: colors.ai + "3a" }]}>
          <Sparkles color={colors.ai} size={15} />
          {modelReady ? (
            <Text style={[styles.aiText, { color: colors.textSecondary }]}>
              NafaIQ setup is <Text style={{ color: colors.ai }}>{t(aiSignal!.signal).toLowerCase()}</Text> with{" "}
              <Text style={{ color: colors.ai }}>{t("Technical setup")}</Text>
            </Text>
          ) : (
            <Text style={[styles.aiText, { color: colors.textSecondary }]}>
              {t("Technical setup unavailable - still warming up")}
            </Text>
          )}
        </View>
      </GlassCard>

      {/* Whole-market AI brief — verified, cited read on today's PSX tape */}
      <AiReportSheet
        title={t("Today's PSX market analysis")}
        subtitle={brief.data?.content?.headline}
        variant="narrative"
        report={brief.data?.content}
        isLoading={brief.isLoading}
        error={brief.error}
        loadingLabel={t("Preparing today's market brief…")}
        emptyLabel={t("Tap for the AI read on today's market")}
        onRefresh={() => brief.refresh()}
        isRefreshing={brief.isRefreshing}
        refreshError={brief.refreshError}
      />

      <Text variant="title">{t("Screener")}</Text>
      <ChipRow options={SIGNALS} value={signal} onChange={(v) => setSignal(v as Signal | "All")} />
    </View>
  );

  const empty = (
    <View style={styles.emptyBox}>
      {snapshotPending ? (
        <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading market data")} />
      ) : (
        <Text variant="muted">
          {snapshotError
            ? t("Could not load market data. Pull to retry later.")
            : signal === "All"
              ? t("No market data available.")
              : t("No stocks match this signal.")}
        </Text>
      )}
    </View>
  );

  const footer = (
    <View style={{ marginTop: 16, gap: 16 }}>
      {/* ── Movers: Gainers / Losers / Most Active ── */}
      <View style={{ gap: 8 }}>
        <Text variant="title">{t("Movers")}</Text>
        <ChipRow options={MOVER_TABS as unknown as string[]} value={moverTab} onChange={(v) => setMoverTab(v as (typeof MOVER_TABS)[number])} />
        {movers.length === 0 ? (
          <View style={styles.emptyBox}>
            {snapshotPending ? (
              <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading market data")} />
            ) : (
              <Text variant="muted">{t("No movers available.")}</Text>
            )}
          </View>
        ) : (
          <FlatList
            horizontal
            data={movers}
            keyExtractor={(m) => m.symbol}
            renderItem={renderMover}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: 10, paddingVertical: 2 }}
          />
        )}
      </View>

      {/* ── Unusual Activity (volume spikes) ── */}
      <View style={{ gap: 8 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Activity color={colors.textSecondary} size={16} />
          <Text variant="title">{t("Unusual Activity")}</Text>
        </View>
        {unusualPending ? (
          <View style={styles.emptyBox}>
            <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading unusual activity")} />
          </View>
        ) : unusualError ? (
          <View style={styles.emptyBox}>
            <Text variant="muted">{t("Could not load unusual activity.")}</Text>
          </View>
        ) : !unusual || unusual.length === 0 ? (
          <View style={styles.emptyBox}>
            <Text variant="muted">{t("No unusual activity right now.")}</Text>
          </View>
        ) : (
          <FlatList
            horizontal
            data={unusual}
            keyExtractor={(u) => `${u.symbol}-${u.ts}`}
            renderItem={renderUnusual}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: 10, paddingVertical: 2 }}
          />
        )}
      </View>

      {/* ── Sector Heatmap (grouped mosaic → drill into a sector's stocks) ── */}
      <SectorHeatmap
        data={treemap}
        isPending={treemapPending}
        isError={treemapError}
        onStockPress={(symbol) => router.push(`/stock/${symbol}`)}
      />

      {/* ── Hub to News / Funds / Dividends / Macro ── */}
      <Pressable
        style={[styles.moreBtn, { borderColor: colors.border }]}
        onPress={() => router.push("/more")}
        accessibilityRole="button"
        accessibilityLabel={t("More: news, funds, dividends and macro")}
      >
        <Text style={{ fontWeight: "600", fontSize: 14 }}>{t("News, Funds, Dividends & Macro")}</Text>
        <ChevronRight color={colors.textMuted} size={18} />
      </Pressable>
    </View>
  );

  return (
    <GlassScreen>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <FlatList
          data={rows}
          keyExtractor={(s) => s.ticker}
          renderItem={renderRow}
          ListHeaderComponent={header}
          ListEmptyComponent={empty}
          ListFooterComponent={footer}
          contentContainerStyle={{ padding: 16, paddingBottom: 28, gap: 8 }}
          showsVerticalScrollIndicator={false}
        />
      </SafeAreaView>
    </GlassScreen>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  indexCard: { width: 150, gap: 2, padding: 12 },
  chartCard: { gap: 12, padding: 16 },
  chartPlaceholder: { height: 220, alignItems: "center", justifyContent: "center" },
  aiBar: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
  aiText: { flex: 1, fontFamily: AVENIR, fontSize: 12.5, lineHeight: 17, fontWeight: "400" },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 11, borderBottomWidth: 1 },
  ticker: { fontWeight: "600", fontSize: 14.5 },
  priceCol: { width: 88, alignItems: "flex-end" },
  sigCol: { width: 96, alignItems: "flex-end", paddingLeft: 8 },
  emptyBox: { paddingVertical: 24, alignItems: "center", justifyContent: "center" },
  moverCard: { width: 118, padding: 12 },
  unusualCard: { width: 170, padding: 12 },
  moreBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
    minHeight: 44,
  },
});
