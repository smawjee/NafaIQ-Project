// Stock detail (`/stock/[ticker]`). Mirrors web `/stock/$ticker`: header,
// candlestick chart, stats grid, AI technical-analysis table, news, actions.
import { useLocalSearchParams } from "expo-router";
import { useMemo } from "react";
import { Alert, StyleSheet, View, useWindowDimensions } from "react-native";

import { Screen } from "@/components/Screen";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { Button, Card, Change, SignalBadge, Text } from "@/components/ui";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { generateOHLCV, type Signal, STOCKS } from "@nafaiq/shared";

const SIGNAL_ROWS: { name: string; value: string; signal: Signal }[] = [
  { name: "RSI (14)", value: "61", signal: "BUY" },
  { name: "MA (20)", value: "Above", signal: "STRONG BUY" },
  { name: "MA (50)", value: "Above", signal: "BUY" },
  { name: "MACD", value: "Bullish cross", signal: "BUY" },
  { name: "Volume", value: "+18% avg", signal: "BUY" },
  { name: "Bollinger", value: "Mid band", signal: "HOLD" },
];

const NEWS = [
  { title: "Bank posts record quarterly profit on higher net interest margin", source: "Business Recorder", time: "2h", sentiment: "positive" },
  { title: "SBP holds policy rate; analysts see banking sector tailwind", source: "Dawn", time: "1d", sentiment: "neutral" },
  { title: "Sector rotation: foreign inflows return to PSX blue chips", source: "Profit", time: "2d", sentiment: "positive" },
];

export default function StockDetailScreen() {
  const { ticker } = useLocalSearchParams<{ ticker: string }>();
  const { colors } = useTheme();
  const { t } = useLang();
  const { width } = useWindowDimensions();
  const stock = STOCKS[(ticker ?? "HBL").toUpperCase()] ?? STOCKS.HBL;

  const candles = useMemo(
    () => generateOHLCV(stock.seed, stock.start, stock.price, 180),
    [stock],
  );

  const stats: [string, string][] = [
    ["Market Cap", stock.marketCap],
    ["P/E", "8.4"],
    ["EPS", "16.9"],
    ["52W High", (stock.price * 1.18).toFixed(2)],
    ["52W Low", (stock.start * 0.92).toFixed(2)],
    ["Avg Volume", stock.volume],
    ["Div Yield", "4.2%"],
    ["RSI", String(stock.rsi)],
  ];

  return (
    <Screen title={stock.ticker} subtitle={`${stock.name} · ${stock.sector}`}>
      <Card style={{ gap: 8 }}>
        <View style={styles.between}>
          <Text variant="mono" style={{ fontSize: 22 }}>
            {stock.price.toFixed(2)}
          </Text>
          <Change pct={stock.changePct} />
        </View>
        <View style={styles.between}>
          <SignalBadge signal={stock.signal} />
          <Text variant="muted">{t("Confidence 5/6 indicators")}</Text>
        </View>
        <CandlestickChart data={candles} width={width - 64} height={200} mas={[{ period: 50, color: colors.info }]} />
      </Card>

      <Card style={{ gap: 0 }}>
        <Text variant="title" style={{ marginBottom: 8 }}>
          {t("Key Stats")}
        </Text>
        <View style={styles.statGrid}>
          {stats.map(([k, v]) => (
            <View key={k} style={styles.statCell}>
              <Text variant="muted">{k}</Text>
              <Text variant="mono" style={{ fontSize: 14 }}>
                {v}
              </Text>
            </View>
          ))}
        </View>
      </Card>

      <Card style={{ gap: 8 }}>
        <Text variant="title">{t("AI Technical Analysis")}</Text>
        {SIGNAL_ROWS.map((r) => (
          <View key={r.name} style={styles.between}>
            <Text variant="secondary" style={{ flex: 1 }}>
              {r.name}
            </Text>
            <Text variant="mono" style={{ flex: 1, textAlign: "center", fontSize: 13 }}>
              {r.value}
            </Text>
            <View style={{ flex: 1, alignItems: "flex-end" }}>
              <SignalBadge signal={r.signal} />
            </View>
          </View>
        ))}
        <View style={[styles.verdict, { borderColor: colors.ai + "44" }]}>
          <Text style={{ color: colors.ai, fontWeight: "700" }}>{t("Overall")}: {t(stock.signal)}</Text>
          <Text variant="secondary">
            {t("Momentum and trend indicators align bullishly. Not financial advice.")}
          </Text>
        </View>
      </Card>

      <Card style={{ gap: 10 }}>
        <Text variant="title">{t("Recent News")}</Text>
        {NEWS.map((n) => (
          <View key={n.title} style={{ gap: 2 }}>
            <Text variant="body">{n.title}</Text>
            <Text variant="muted">
              {n.source} · {n.time} ·{" "}
              <Text style={{ color: n.sentiment === "positive" ? colors.bull : colors.neutral }}>
                {n.sentiment}
              </Text>
            </Text>
          </View>
        ))}
      </Card>

      <View style={{ gap: 10 }}>
        <Button title={t("Add to Watchlist")} onPress={() => Alert.alert("Watchlist", `${stock.ticker} added (demo)`)} />
        <Button title={t("Add to Portfolio")} variant="outline" onPress={() => Alert.alert("Portfolio", "Demo only")} />
        <Button title={t("Set Price Alert")} variant="ghost" onPress={() => Alert.alert("Alert", "Demo only")} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statGrid: { flexDirection: "row", flexWrap: "wrap" },
  statCell: { width: "25%", paddingVertical: 6, gap: 2 },
  verdict: { borderWidth: 1, borderRadius: 10, padding: 10, gap: 4, marginTop: 4 },
});
