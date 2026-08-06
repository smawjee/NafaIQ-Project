import { useLocalSearchParams } from "expo-router";
import { useMemo } from "react";
import { ActivityIndicator, StyleSheet, View, useWindowDimensions } from "react-native";

import { Sparkline } from "@/components/charts/Sparkline";
import { GlassCard } from "@/components/glass/GlassCard";
import { Screen } from "@/components/Screen";
import { Button, Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useFund, useFundNav } from "@/hooks/queries/use-funds";
import { useTheme } from "@/hooks/use-theme";
import { Landmark, ShieldCheck } from "@/lib/icons";
import { fmtPKR } from "@nafaiq/shared";

export default function FundDetailScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const fundCode = decodeURIComponent(code ?? "");
  const { colors } = useTheme();
  const { width } = useWindowDimensions();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const fund = useFund(fundCode);
  const nav = useFundNav(fundCode);
  const chronological = useMemo(() => (nav.data ?? []).slice().reverse(), [nav.data]);
  const series = useMemo(() => chronological.map((point) => point.nav).filter(Number.isFinite), [chronological]);
  const first = series[0];
  const latest = series[series.length - 1];
  const changePct = first && latest ? ((latest - first) / first) * 100 : null;

  return (
    <Screen title={fund.data?.name ?? fundCode} subtitle={[fund.data?.category, fund.data?.amc].filter(Boolean).join(" · ")} back>
      {fund.isPending ? <ActivityIndicator color={colors.primary} /> : fund.isError ? <GlassCard><Text variant="secondary">Could not load this fund.</Text><Button title="Retry" onPress={() => fund.refetch()} /></GlassCard> : (
        <GlassCard style={{ gap: 14 }}>
          <View style={styles.between}>
            <View style={styles.fundIcon}><Landmark color={colors.primary} size={20} /></View>
            {fund.data?.shariah ? <View style={styles.shariah}><ShieldCheck color={colors.bull} size={13} /><Text style={{ color: colors.bull, fontSize: 10, fontWeight: "700" }}>SHARIAH</Text></View> : null}
          </View>
          <View><Text variant="muted">LATEST NAV</Text><Text style={styles.nav}>{fund.data?.latest_nav != null ? fmtPKR(fund.data.latest_nav, 2) : "—"}</Text><Text variant="muted">{fund.data?.nav_date ?? "Date unavailable"}</Text></View>
          {series.length > 1 ? <><Sparkline data={series} width={Math.max(180, width - 70)} height={100} /><Text style={{ color: (changePct ?? 0) >= 0 ? colors.bull : colors.bear, fontFamily: fonts.mono, fontSize: 12 }}>{changePct == null ? "—" : `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}% over available history`}</Text></> : null}
        </GlassCard>
      )}

      <Text variant="title">NAV history</Text>
      {nav.isPending ? <ActivityIndicator color={colors.primary} /> : nav.isError ? <GlassCard><Text variant="secondary">Could not load NAV history.</Text><Button title="Retry" variant="outline" onPress={() => nav.refetch()} /></GlassCard> : chronological.length === 0 ? <GlassCard><Text variant="secondary">No NAV history is available.</Text></GlassCard> : (
        <GlassCard style={{ padding: 0, overflow: "hidden" }}>
          <View style={[styles.row, styles.head]}><Text variant="muted">DATE</Text><Text variant="muted">NAV</Text></View>
          {chronological.slice(-40).reverse().map((point) => <View key={point.date} style={styles.row}><Text variant="mono" style={{ fontSize: 12 }}>{point.date}</Text><Text variant="mono" style={{ fontSize: 12 }}>{fmtPKR(point.nav, 2)}</Text></View>)}
        </GlassCard>
      )}
    </Screen>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  between: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  fundIcon: { width: 44, height: 44, borderRadius: 12, borderWidth: 1, borderColor: c.primary + "44", backgroundColor: c.primary + "12", alignItems: "center", justifyContent: "center" },
  shariah: { flexDirection: "row", alignItems: "center", gap: 5, borderWidth: 1, borderColor: c.bull + "55", borderRadius: 999, paddingHorizontal: 8, paddingVertical: 5 },
  nav: { fontFamily: fonts.heading, fontSize: 28, fontWeight: "800", marginVertical: 4 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 42, paddingHorizontal: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: c.border },
  head: { backgroundColor: c.glassFillStrong },
});
