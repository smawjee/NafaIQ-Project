// Stock detail (`/stock/[ticker]`). Mirrors web `src/features/stock/StockDetail.tsx`:
// header, candlestick chart, stats grid (live fundamentals), ML signal verdict,
// recent announcements, actions. Live data via src/hooks/queries/use-market.ts.
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, StyleSheet, View, useWindowDimensions } from "react-native";

import { Screen } from "@/components/Screen";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { Button, Card, Change, SignalBadge, Text } from "@/components/ui";
import {
  usePsxAnnouncements,
  usePsxCompanyProfile,
  usePsxFundamentals,
  usePsxHistory,
  usePsxQuote,
  usePsxSignal,
  usePsxSymbols,
} from "@/hooks/queries/use-market";
import { useWatchlist } from "@/hooks/queries/use-watchlist";
import { useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { fmtNum } from "@nafaiq/shared";

/** Compact PKR (mirrors web formatCompactPKR), e.g. 2.15e11 -> "PKR 215B". */
function compactPKR(value: number): string {
  const abs = Math.abs(value);
  const units: [number, string][] = [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  for (const [threshold, suffix] of units) {
    if (abs >= threshold) {
      const scaled = abs / threshold;
      return `PKR ${scaled.toFixed(scaled < 100 ? 1 : 0)}${suffix}`;
    }
  }
  return `PKR ${fmtNum(value, 0)}`;
}

/** Relative time for announcement rows (mirrors web formatTimeAgo). */
function formatTimeAgo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

export default function StockDetailScreen() {
  const { ticker } = useLocalSearchParams<{ ticker: string }>();
  const { colors } = useTheme();
  const { t } = useLang();
  const { width } = useWindowDimensions();
  const upper = (ticker ?? "HBL").toUpperCase();

  const { data: quote } = usePsxQuote(upper);
  const { data: candles, isPending: candlesPending } = usePsxHistory(upper, 180);
  const { data: profile } = usePsxCompanyProfile(upper);
  const { data: fundamentals } = usePsxFundamentals(upper);
  const { data: announcements, isPending: newsPending } = usePsxAnnouncements(upper, 5);
  const { data: signal } = usePsxSignal(upper);
  const { data: symbolsData } = usePsxSymbols();
  const wl = useWatchlist();
  const [wlBusy, setWlBusy] = useState(false);

  const symbolInfo = symbolsData?.find((x) => x.symbol === upper);

  // Canonical company name: prefer a real name from profile/symbols; never
  // echo the ticker back (avoids "HBL · HBL").
  const rawName = profile?.name || symbolInfo?.name || "";
  const name = rawName && rawName.toUpperCase() !== upper ? rawName : "";
  const sector = profile?.sector ?? symbolInfo?.sector ?? null;

  const price = quote?.price ?? null;
  const changePct = quote?.change_pct ?? null;

  // Signal: only trust the model when it is trained — a pending model shows
  // no fake call (same rule as web).
  const modelReady = !!signal && signal.model_version !== "fallback";
  const confidence = signal?.confidence ?? 0;

  const marketCap =
    profile?.listed_shares && price != null ? compactPKR(profile.listed_shares * price) : "—";

  const stats: [string, string][] = [
    ["Market Cap", marketCap],
    ["P/E", fundamentals?.pe != null ? fundamentals.pe.toFixed(1) : "—"],
    ["EPS", fundamentals?.eps != null ? fundamentals.eps.toFixed(2) : "—"],
    ["Day High", quote?.day_high != null ? fmtNum(quote.day_high) : "—"],
    ["Day Low", quote?.day_low != null ? fmtNum(quote.day_low) : "—"],
    ["Volume", quote?.volume != null ? fmtNum(quote.volume, 0) : "—"],
    ["Div Yield", fundamentals?.div_yield != null ? `${fundamentals.div_yield.toFixed(1)}%` : "—"],
    ["P/B", fundamentals?.pb != null ? fundamentals.pb.toFixed(2) : "—"],
  ];

  const isInWatchlist = wl.symbols.includes(upper);

  const toggleWatchlist = async () => {
    if (wlBusy) return;
    setWlBusy(true);
    const wasIn = isInWatchlist;
    try {
      if (wasIn) await wl.remove(upper);
      else await wl.add(upper);
    } catch {
      Alert.alert(t("Watchlist"), t("Something went wrong. Please try again."));
    } finally {
      setWlBusy(false);
    }
  };

  const subtitle = [name, sector ? t(sector) : null].filter(Boolean).join(" · ");

  return (
    <Screen title={upper} subtitle={subtitle || t("Pakistan Stock Exchange")}>
      <Card style={{ gap: 8 }}>
        <View style={styles.between}>
          <Text variant="mono" style={{ fontSize: 22 }}>
            {price != null ? fmtNum(price) : "—"}
          </Text>
          {changePct != null && <Change pct={changePct} />}
        </View>
        <View style={styles.between}>
          {modelReady ? (
            <SignalBadge signal={signal!.signal} />
          ) : (
            <Text variant="muted">{t("Signal unavailable")}</Text>
          )}
          <Text variant="muted">
            {modelReady
              ? `${t("Confidence")} ${Math.round(confidence)}%`
              : t("Model training in progress")}
          </Text>
        </View>
        {candlesPending ? (
          <View style={styles.chartPlaceholder} accessibilityLabel={t("Loading chart data")}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : candles && candles.length > 0 ? (
          <CandlestickChart data={candles} width={width - 64} height={200} mas={[{ period: 50, color: colors.info }]} />
        ) : (
          <View style={styles.chartPlaceholder}>
            <Text variant="muted">{t("No chart data available.")}</Text>
          </View>
        )}
      </Card>

      <Card style={{ gap: 0 }}>
        <Text variant="title" style={{ marginBottom: 8 }}>
          {t("Key Stats")}
        </Text>
        <View style={styles.statGrid}>
          {stats.map(([k, v]) => (
            <View key={k} style={styles.statCell}>
              <Text variant="muted">{t(k)}</Text>
              <Text variant="mono" style={{ fontSize: 14 }}>
                {v}
              </Text>
            </View>
          ))}
        </View>
      </Card>

      <Card style={{ gap: 8 }}>
        <Text variant="title">{t("AI Technical Analysis")}</Text>
        {modelReady ? (
          <>
            <View style={[styles.verdict, { borderColor: colors.ai + "44" }]}>
              <Text style={{ color: colors.ai, fontWeight: "700" }}>
                {t("Overall")}: {t(signal!.signal)} · {t("Confidence")} {Math.round(confidence)}%
              </Text>
              <Text variant="secondary">
                {`${upper} — ${t("ML signal engine rates this stock")} ${t(signal!.signal)}. ${t("Key drivers")}: ${
                  signal!.features_used?.slice(0, 3).join(", ") || t("technical indicators")
                }.`}
              </Text>
            </View>
            <Text variant="muted" style={{ fontStyle: "italic" }}>
              {t("This is AI-generated technical analysis only. Not financial advice.")}
            </Text>
          </>
        ) : (
          <View style={[styles.pending, { borderColor: colors.border }]}>
            <Text variant="secondary" style={{ fontWeight: "600" }}>
              {t("Signal unavailable — model pending")}
            </Text>
            <Text variant="muted">
              {t("The ML signal model has not produced a call for this stock yet.")}
            </Text>
          </View>
        )}
      </Card>

      <Card style={{ gap: 10 }}>
        <Text variant="title">{t("Recent Announcements")}</Text>
        {newsPending ? (
          <ActivityIndicator color={colors.primary} accessibilityLabel={t("Loading announcements")} />
        ) : announcements && announcements.length > 0 ? (
          announcements.map((n) => {
            const inner = (
              <View style={{ gap: 2 }}>
                <Text variant="body" numberOfLines={2}>{n.title}</Text>
                <Text variant="muted">
                  {t(n.category ?? "Corporate")} · {formatTimeAgo(n.posted_at)}
                </Text>
              </View>
            );
            return n.url ? (
              <Pressable
                key={n.id}
                onPress={() => Linking.openURL(n.url!)}
                accessibilityRole="link"
                accessibilityLabel={n.title}
                style={({ pressed }) => [styles.newsRow, pressed && { opacity: 0.7 }]}
              >
                {inner}
              </Pressable>
            ) : (
              <View key={n.id} style={styles.newsRow}>
                {inner}
              </View>
            );
          })
        ) : (
          <Text variant="muted" style={{ paddingVertical: 4 }}>
            {t("No recent announcements.")}
          </Text>
        )}
      </Card>

      <View style={{ gap: 10 }}>
        <Button
          title={isInWatchlist ? t("Remove from Watchlist") : t("Add to Watchlist")}
          loading={wlBusy || wl.loading}
          onPress={toggleWatchlist}
        />
        <Button title={t("Add to Portfolio")} variant="outline" onPress={() => Alert.alert(t("Portfolio"), t("Manage holdings from the Portfolio tab."))} />
        <Button title={t("Set Price Alert")} variant="ghost" onPress={() => Alert.alert(t("Alerts"), t("Create price alerts from the Alerts screen."))} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  statGrid: { flexDirection: "row", flexWrap: "wrap" },
  statCell: { width: "25%", paddingVertical: 6, gap: 2 },
  chartPlaceholder: { height: 200, alignItems: "center", justifyContent: "center" },
  verdict: { borderWidth: 1, borderRadius: 10, padding: 10, gap: 4, marginTop: 4 },
  pending: { borderWidth: 1, borderStyle: "dashed", borderRadius: 10, padding: 12, gap: 4, alignItems: "center" },
  newsRow: { gap: 2, minHeight: 44, justifyContent: "center" },
});
