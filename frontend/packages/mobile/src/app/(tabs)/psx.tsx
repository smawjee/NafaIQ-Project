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
import { SignalBadge, Text } from "@/components/ui";
import { Chip, ChipRow, Segmented } from "@/components/ui/controls";
import { fonts } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import {
  useIndexCards,
  usePsxBatchSignals,
  usePsxHistory,
  usePsxLiveMarket,
  usePsxRealtime,
  usePsxScreenerMetrics,
  usePsxSectors,
  usePsxSignal,
  usePsxSymbols,
} from "@/hooks/queries/use-market";
import { useMarketBrief } from "@/hooks/ai/use-market-brief";
import { useTheme } from "@/hooks/use-theme";
import { Sparkles } from "@/lib/icons";
import { fmtNum, type Signal } from "@nafaiq/shared";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

const TIMEFRAMES: Record<string, number> = { "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 260 };
const SIGNALS: (Signal | "All")[] = ["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"];

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

  usePsxRealtime();
  const { data: snapshot, isPending: snapshotPending, isError: snapshotError } = usePsxLiveMarket();
  const { data: symbolsData } = usePsxSymbols();
  const { data: batchSignals } = usePsxBatchSignals(50);
  const { data: screenerMetrics } = usePsxScreenerMetrics();
  const { data: sectorData, isPending: sectorsPending } = usePsxSectors();
  const { data: candles, isPending: candlesPending, isError: candlesError } = usePsxHistory(
    sym,
    TIMEFRAMES[tf],
  );
  const { data: aiSignal } = usePsxSignal(sym);
  const brief = useMarketBrief();
  const indexCards = useIndexCards();

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

  const modelReady = !!aiSignal && aiSignal.model_version !== "fallback";

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

  const header = (
    <View style={{ gap: 16 }}>
      <Text variant="display" style={{ fontFamily: AVENIR }}>{t("PSX Market")}</Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
        {indexCards.map((idx) => (
          <GlassCard key={idx.name} radius={16} intensity={18} style={styles.indexCard}>
            <Text variant="muted">{idx.name}</Text>
            <Text variant="mono" style={{ fontSize: 16, marginVertical: 2 }}>
              {idx.value > 0 ? idx.value.toLocaleString() : "—"}
            </Text>
            <Text style={{ color: idx.changePct >= 0 ? colors.bull : colors.bear, fontSize: 12 }}>
              {idx.changePct >= 0 ? "▲" : "▼"} {Math.abs(idx.changePct).toFixed(2)}%
            </Text>
            <Sparkline data={new Array(7).fill(idx.value)} width={120} height={28} />
          </GlassCard>
        ))}
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
              The AI recommends a <Text style={{ color: colors.ai }}>{t(aiSignal!.signal).toLowerCase()}</Text> with{" "}
              <Text style={{ color: colors.ai }}>{Math.round(aiSignal!.confidence)}% confidence</Text>
            </Text>
          ) : (
            <Text style={[styles.aiText, { color: colors.textSecondary }]}>
              {t("AI signal unavailable — model training in progress")}
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
    <View style={{ marginTop: 16, gap: 8 }}>
      <Text variant="title">{t("Sector Heatmap")}</Text>
      {sectorsPending ? (
        <View style={styles.emptyBox}>
          <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading sectors")} />
        </View>
      ) : !sectorData || sectorData.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text variant="muted">{t("No sector data available.")}</Text>
        </View>
      ) : (
        <View style={styles.heatGrid}>
          {sectorData.map((s) => {
            const up = s.pct >= 0;
            const intensity = Math.min(0.5, Math.abs(s.pct) / 6 + 0.12);
            return (
              <View
                key={s.name}
                style={[styles.heatCell, { backgroundColor: (up ? colors.bull : colors.bear) + Math.round(intensity * 255).toString(16).padStart(2, "0") }]}
              >
                <Text style={{ fontSize: 12, fontWeight: "600" }} numberOfLines={1}>{s.name}</Text>
                <Text variant="mono" style={{ fontSize: 12 }}>
                  {up ? "+" : ""}
                  {s.pct.toFixed(2)}%
                </Text>
              </View>
            );
          })}
        </View>
      )}
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
  heatGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  heatCell: { width: "31%", borderRadius: 10, padding: 10, gap: 2 },
});
