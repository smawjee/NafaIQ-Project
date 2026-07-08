// PSX Market Terminal (`/psx`): index cards, price chart with candle/line toggle
// + symbol/timeframe/MA controls, AI bar, screener (signal filters), sector
// heatmap. Single FlatList for virtualization. Theme + i18n aware.
import { useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { FlatList, Platform, Pressable, ScrollView, StyleSheet, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { PriceLineChart } from "@/components/charts/PriceLineChart";
import { Sparkline } from "@/components/charts/Sparkline";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { SignalBadge, Text } from "@/components/ui";
import { Chip, ChipRow, Segmented } from "@/components/ui/controls";
import { fonts } from "@/constants/theme";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { generateOHLCV, INDICES, SECTORS, type Signal, STOCK_LIST, STOCKS } from "@nafaiq/shared";
import { Sparkles } from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

const TIMEFRAMES: Record<string, number> = { "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 260 };
const SIGNALS: (Signal | "All")[] = ["All", "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"];

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

  const stock = STOCKS[sym];
  const candles = useMemo(() => generateOHLCV(stock.seed, stock.start, stock.price, TIMEFRAMES[tf]), [stock, tf]);
  const mas = useMemo(
    () =>
      [ma20 ? { period: 20, color: colors.warning } : null, ma50 ? { period: 50, color: colors.info } : null].filter(
        Boolean,
      ) as { period: number; color: string }[],
    [ma20, ma50, colors],
  );

  const rows = useMemo(
    () => (signal === "All" ? STOCK_LIST : STOCK_LIST.filter((s) => s.signal === signal)),
    [signal],
  );

  const renderRow = useCallback(
    ({ item }: { item: (typeof STOCK_LIST)[number] }) => (
      <Pressable
        style={[styles.row, { borderBottomColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel={`${item.ticker}, ${item.signal}, RSI ${item.rsi}`}
        onPress={() => router.push(`/stock/${item.ticker}`)}
      >
        <View style={{ flex: 1 }}>
          <Text style={styles.ticker}>{item.ticker}</Text>
          <Text variant="muted">{item.sector}</Text>
        </View>
        <View style={styles.priceCol}>
          <Text variant="mono" style={{ fontSize: 13.5 }}>{item.price.toFixed(2)}</Text>
          <Text style={{ fontSize: 12, marginTop: 2, fontFamily: fonts.mono, color: item.changePct >= 0 ? colors.bull : colors.bear }}>
            {item.changePct >= 0 ? "+" : ""}
            {item.changePct}%
          </Text>
        </View>
        <View style={styles.sigCol}>
          <SignalBadge signal={item.signal} />
        </View>
      </Pressable>
    ),
    [router, colors],
  );

  const header = (
    <View style={{ gap: 16 }}>
      <Text variant="display" style={{ fontFamily: AVENIR }}>{t("PSX Market")}</Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>
        {INDICES.map((idx) => {
          const series = generateOHLCV(idx.seed, idx.start, idx.end, 24).map((c) => c.close);
          return (
            <GlassCard key={idx.name} radius={16} intensity={18} style={styles.indexCard}>
              <Text variant="muted">{idx.name}</Text>
              <Text variant="mono" style={{ fontSize: 16, marginVertical: 2 }}>{idx.value.toLocaleString()}</Text>
              <Text style={{ color: idx.changePct >= 0 ? colors.bull : colors.bear, fontSize: 12 }}>
                {idx.changePct >= 0 ? "▲" : "▼"} {Math.abs(idx.changePct)}%
              </Text>
              <Sparkline data={series} width={120} height={28} />
            </GlassCard>
          );
        })}
      </ScrollView>

      <GlassCard style={styles.chartCard}>
        <View style={styles.between}>
          <View>
            <Text variant="title">{stock.ticker}</Text>
            <Text variant="muted">{stock.name}</Text>
          </View>
          <SignalBadge signal={stock.signal} />
        </View>
        <ChipRow options={STOCK_LIST.map((s) => s.ticker)} value={sym} onChange={setSym} />
        <Segmented options={Object.keys(TIMEFRAMES)} value={tf} onChange={setTf} />
        <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
          <View style={{ flex: 1 }}>
            <Segmented options={["Candle", "Line"]} value={chartType} onChange={setChartType} />
          </View>
          <Chip label="MA20" active={ma20} onPress={() => setMa20((v) => !v)} color={colors.warning} />
          <Chip label="MA50" active={ma50} onPress={() => setMa50((v) => !v)} color={colors.info} />
        </View>
        {chartType === "Candle" ? (
          <CandlestickChart data={candles} width={chartW} mas={mas} />
        ) : (
          <PriceLineChart data={candles} width={chartW} mas={mas} />
        )}
        <View style={[styles.aiBar, { backgroundColor: colors.ai + "12", borderColor: colors.ai + "3a" }]}>
          <Sparkles color={colors.ai} size={15} />
          <Text style={[styles.aiText, { color: colors.textSecondary }]}>
            The AI recommends a <Text style={{ color: colors.ai }}>{t(stock.signal).toLowerCase()}</Text> with{" "}
            <Text style={{ color: colors.ai }}>72% confidence</Text>
          </Text>
        </View>
      </GlassCard>

      <Text variant="title">{t("Screener")}</Text>
      <ChipRow options={SIGNALS} value={signal} onChange={(v) => setSignal(v as Signal | "All")} />
    </View>
  );

  const footer = (
    <View style={{ marginTop: 16, gap: 8 }}>
      <Text variant="title">{t("Sector Heatmap")}</Text>
      <View style={styles.heatGrid}>
        {SECTORS.map((s) => {
          const up = s.pct >= 0;
          const intensity = Math.min(0.5, Math.abs(s.pct) / 6 + 0.12);
          return (
            <View
              key={s.name}
              style={[styles.heatCell, { backgroundColor: (up ? colors.bull : colors.bear) + Math.round(intensity * 255).toString(16).padStart(2, "0") }]}
            >
              <Text style={{ fontSize: 12, fontWeight: "600" }}>{s.name}</Text>
              <Text variant="mono" style={{ fontSize: 12 }}>
                {up ? "+" : ""}
                {s.pct}%
              </Text>
            </View>
          );
        })}
      </View>
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
  aiBar: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
  aiText: { flex: 1, fontFamily: AVENIR, fontSize: 12.5, lineHeight: 17, fontWeight: "400" },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 11, borderBottomWidth: 1 },
  ticker: { fontWeight: "600", fontSize: 14.5 },
  priceCol: { width: 88, alignItems: "flex-end" },
  sigCol: { width: 96, alignItems: "flex-end", paddingLeft: 8 },
  heatGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  heatCell: { width: "31%", borderRadius: 10, padding: 10, gap: 2 },
});

