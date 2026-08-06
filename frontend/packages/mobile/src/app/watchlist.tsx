import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, TextInput, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { Screen } from "@/components/Screen";
import { Button, Change, Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { usePsxSymbols } from "@/hooks/queries/use-market";
import { useAddToWatchlist, useClearWatchlist, useEnrichedWatchlist, useRemoveFromWatchlist } from "@/hooks/queries/use-watchlist";
import { useTheme } from "@/hooks/use-theme";
import { Plus, Search, Trash2, X } from "@/lib/icons";
import { fmtNum } from "@nafaiq/shared";

export default function WatchlistScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const watch = useEnrichedWatchlist();
  const symbols = usePsxSymbols();
  const add = useAddToWatchlist();
  const remove = useRemoveFromWatchlist();
  const clear = useClearWatchlist();
  const [search, setSearch] = useState("");
  const existing = useMemo(() => new Set((watch.data ?? []).map((item) => item.symbol)), [watch.data]);
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (q.length < 1) return [];
    return (symbols.data ?? []).filter((item) => !existing.has(item.symbol) && (item.symbol.toLowerCase().includes(q) || item.name?.toLowerCase().includes(q))).slice(0, 8);
  }, [search, symbols.data, existing]);

  function confirmClear() {
    Alert.alert("Clear watchlist?", "This removes every watched symbol.", [
      { text: "Cancel", style: "cancel" },
      { text: "Clear all", style: "destructive", onPress: () => clear.mutate() },
    ]);
  }

  return (
    <Screen title="Watchlist" subtitle="Live prices and the PSX names you care about." back>
      <GlassCard style={{ gap: 10 }}>
        <View style={styles.search}>
          <Search color={colors.textMuted} size={17} />
          <TextInput value={search} onChangeText={setSearch} placeholder="Add a symbol or company" placeholderTextColor={colors.textMuted} style={styles.input} accessibilityLabel="Search symbols to add" />
        </View>
        {matches.map((item) => (
          <Pressable key={item.symbol} onPress={() => add.mutate(item.symbol, { onSuccess: () => setSearch("") })} style={styles.suggestion} accessibilityRole="button">
            <View style={{ flex: 1 }}><Text style={{ fontWeight: "800" }}>{item.symbol}</Text><Text variant="muted" numberOfLines={1}>{item.name}</Text></View>
            <Plus color={colors.primary} size={18} />
          </Pressable>
        ))}
      </GlassCard>

      {(watch.data?.length ?? 0) > 0 ? <View style={styles.between}><Text variant="title">{watch.data!.length} watched</Text><Button title="Clear all" variant="ghost" onPress={confirmClear} loading={clear.isPending} icon={<Trash2 color={colors.bear} size={15} />} /></View> : null}

      {watch.isPending ? <ActivityIndicator color={colors.primary} /> : watch.isError ? <GlassCard><Text variant="secondary">Could not load your watchlist.</Text><Button title="Retry" onPress={() => watch.refetch()} /></GlassCard> : (watch.data?.length ?? 0) === 0 ? <GlassCard style={styles.empty}><Search color={colors.textMuted} size={24} /><Text variant="secondary">Search above to build your watchlist.</Text></GlassCard> : watch.data!.map((item) => (
        <Pressable key={item.symbol} onPress={() => router.push(`/stock/${item.symbol}`)} accessibilityRole="button">
          <GlassCard style={styles.row}>
            <View style={{ flex: 1, gap: 3 }}><Text style={{ fontFamily: fonts.heading, fontWeight: "800", fontSize: 16 }}>{item.symbol}</Text><Text variant="muted" numberOfLines={1}>{item.company_name} · {item.sector}</Text></View>
            <View style={{ alignItems: "flex-end" }}><Text variant="mono">{item.price != null ? fmtNum(item.price) : "—"}</Text>{item.change_pct != null ? <Change pct={item.change_pct} /> : null}</View>
            <Pressable onPress={(event) => { event.stopPropagation(); remove.mutate(item.symbol); }} hitSlop={12} accessibilityRole="button" accessibilityLabel={`Remove ${item.symbol}`}><X color={colors.textMuted} size={16} /></Pressable>
          </GlassCard>
        </Pressable>
      ))}
    </Screen>
  );
}

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  search: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 9, borderWidth: 1, borderColor: c.border, borderRadius: 11, backgroundColor: c.glassFill, paddingHorizontal: 12 },
  input: { flex: 1, color: c.textPrimary, minHeight: 46 },
  suggestion: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.border },
  between: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  empty: { alignItems: "center", gap: 10, paddingVertical: 28 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, padding: 14 },
});
