import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import { AiReportSheet } from "@/components/ai/AiReportSheet";
import { GlassCard } from "@/components/glass/GlassCard";
import { Screen } from "@/components/Screen";
import { Button, Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useFinanceReport, usePortfolioReport } from "@/hooks/ai/use-ai-report";
import { useMarketBrief } from "@/hooks/ai/use-market-brief";
import { usePsxSymbols } from "@/hooks/queries/use-market";
import { useTheme } from "@/hooks/use-theme";
import { Bot, ChevronRight, Search, Sparkles } from "@/lib/icons";

export default function AiInsightsScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const market = useMarketBrief();
  const portfolio = usePortfolioReport(180);
  const finance = useFinanceReport();
  const symbols = usePsxSymbols();
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return (symbols.data ?? []).filter((item) => item.symbol.toLowerCase().includes(q) || item.name?.toLowerCase().includes(q)).slice(0, 6);
  }, [query, symbols.data]);

  return (
    <Screen title="AI Insights" subtitle="One place for verified market and personal intelligence." back>
      <GlassCard style={styles.hero}>
        <View style={styles.heroIcon}><Sparkles color={colors.primary} size={22} /></View>
        <View style={{ flex: 1 }}><Text variant="title" style={{ fontFamily: fonts.heading }}>Your intelligence desk</Text><Text variant="secondary" style={{ fontSize: 13 }}>Reports stay separate from deterministic market signals and cite their data.</Text></View>
      </GlassCard>

      <AiReportSheet
        title="Today's Market Brief"
        subtitle={market.data?.content?.headline ?? "PSX breadth, movers, and market context"}
        report={market.data?.content}
        isLoading={market.isPending || market.isRefreshing}
        error={market.error ?? market.refreshError}
        loadingLabel="Preparing today's market brief…"
        emptyLabel="Open the latest verified market brief"
        onOpen={() => { if (!market.data && !market.isFetching) market.refetch(); }}
      />
      <AiReportSheet
        title="Portfolio Intelligence"
        subtitle={portfolio.data?.content?.headline ?? "Concentration, performance, and risk review"}
        report={portfolio.data?.content}
        isLoading={portfolio.isPending}
        error={portfolio.error}
        loadingLabel="Analysing your portfolio…"
        emptyLabel="Generate a verified portfolio report"
        onOpen={() => { if (!portfolio.data && !portfolio.isPending) portfolio.mutate(); }}
      />
      <AiReportSheet
        title="Finance Intelligence"
        subtitle={finance.data?.content?.headline ?? "Cash flow, budgets, bills, and goal progress"}
        report={finance.data?.content}
        isLoading={finance.isPending}
        error={finance.error}
        loadingLabel="Reviewing your finances…"
        emptyLabel="Generate a verified finance report"
        onOpen={() => { if (!finance.data && !finance.isPending) finance.mutate(); }}
      />

      <GlassCard style={{ gap: 10 }}>
        <Text variant="title">Analyse a stock</Text>
        <View style={styles.search}><Search color={colors.textMuted} size={17} /><TextInput value={query} onChangeText={setQuery} placeholder="Symbol or company" placeholderTextColor={colors.textMuted} style={styles.input} accessibilityLabel="Search a stock for AI analysis" /></View>
        {results.map((item) => <Pressable key={item.symbol} onPress={() => router.push(`/stock/${item.symbol}`)} style={styles.result} accessibilityRole="button"><View style={{ flex: 1 }}><Text style={{ fontWeight: "800" }}>{item.symbol}</Text><Text variant="muted" numberOfLines={1}>{item.name}</Text></View><ChevronRight color={colors.primary} size={17} /></Pressable>)}
      </GlassCard>

      <GlassCard style={styles.assistant}>
        <View style={styles.heroIcon}><Bot color={colors.primary} size={21} /></View>
        <View style={{ flex: 1 }}><Text variant="title">Ask NafaIQ</Text><Text variant="secondary" style={{ fontSize: 13 }}>Explore the reports conversationally or draft a safe action.</Text></View>
        <Button title="Open" variant="outline" onPress={() => router.push("/assistant")} />
      </GlassCard>
    </Screen>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  hero: { flexDirection: "row", alignItems: "center", gap: 12, borderColor: c.primary + "33" },
  heroIcon: { width: 44, height: 44, borderRadius: 13, borderWidth: 1, borderColor: c.primary + "44", backgroundColor: c.primary + "12", alignItems: "center", justifyContent: "center" },
  search: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderColor: c.border, borderRadius: 10, backgroundColor: c.glassFill, paddingHorizontal: 12 },
  input: { flex: 1, minHeight: 46, color: c.textPrimary },
  result: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.border, paddingHorizontal: 6 },
  assistant: { flexDirection: "row", alignItems: "center", gap: 12 },
});
