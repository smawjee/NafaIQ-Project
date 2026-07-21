// Dividends (`/dividends`): virtualized calendar of PSX dividend announcements
// from GET /api/dividends via useDividends(). Each row shows the symbol, payout
// type, per-share / bonus, and ex-/announcement dates. Tapping a row opens the
// stock detail. Mirrors web features/dividends DividendCalendar.
import { Stack, useRouter } from "expo-router";
import { useCallback, useMemo } from "react";
import { ActivityIndicator, FlatList, Platform, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Card, Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { type ApiDividendEvent, useDividends } from "@/hooks/queries/use-dividends";
import { useTheme } from "@/hooks/use-theme";
import { ArrowLeft, ChevronRight, Coins } from "@/lib/icons";
import { fmtNum } from "@nafaiq/shared";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function DividendsScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const { data, isPending, isError, refetch } = useDividends();

  // Most recent ex-date first — same ordering as the web calendar.
  const events = useMemo(
    () =>
      [...(data ?? [])].sort(
        (a, b) => new Date(b.ex_date ?? 0).getTime() - new Date(a.ex_date ?? 0).getTime(),
      ),
    [data],
  );

  const renderItem = useCallback(
    ({ item }: { item: ApiDividendEvent }) => {
      const payout =
        item.per_share != null
          ? `PKR ${fmtNum(item.per_share, 2)} / share`
          : item.bonus_pct != null
            ? `${fmtNum(item.bonus_pct, 0)}% bonus`
            : "—";
      return (
        <Pressable
          onPress={() => router.push(`/stock/${item.symbol}` as never)}
          accessibilityRole="button"
          accessibilityLabel={`${item.symbol}, ${item.payout_type}, ${payout}, ex-date ${fmtDate(item.ex_date)}`}
          style={({ pressed }) => [styles.row, pressed ? { backgroundColor: colors.hover } : null]}
        >
          <View style={styles.iconBox}>
            <Coins color={colors.primary} size={16} />
          </View>
          <View style={{ flex: 1, gap: 3 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Text style={{ fontWeight: "700", color: colors.bull }}>{item.symbol}</Text>
              <Text variant="muted">{item.payout_type}</Text>
            </View>
            <Text variant="secondary" style={{ fontSize: 13 }}>
              {payout}
            </Text>
            <Text variant="muted">
              Ex: {fmtDate(item.ex_date)} · Announced: {fmtDate(item.announcement_date)}
            </Text>
          </View>
          <ChevronRight color={colors.textMuted} size={18} />
        </Pressable>
      );
    },
    [styles, colors, router],
  );

  return (
    <GlassScreen>
      <Stack.Screen options={{ headerShown: false }} />
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <View style={styles.header}>
          <Pressable
            onPress={() => router.back()}
            hitSlop={12}
            style={styles.backBtn}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <ArrowLeft color={colors.textPrimary} size={22} />
          </Pressable>
          <Text variant="display" style={{ fontFamily: AVENIR }}>
            Dividends
          </Text>
        </View>

        <FlatList
          data={isPending ? [] : events}
          keyExtractor={(d) => `${d.symbol}-${d.announcement_id}`}
          renderItem={renderItem}
          ItemSeparatorComponent={() => <View style={styles.sep} />}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={
            !isPending && !isError && events.length > 0 ? (
              <Text variant="muted" style={{ marginBottom: 8 }}>
                Recent dividend announcements across PSX.
              </Text>
            ) : null
          }
          ListEmptyComponent={
            isPending ? (
              <Card style={styles.center}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading dividends" />
              </Card>
            ) : isError ? (
              <Card style={styles.center}>
                <Text variant="secondary">Could not load dividend data.</Text>
                <Button title="Retry" variant="outline" onPress={() => refetch()} />
              </Card>
            ) : (
              <Card style={styles.center}>
                <Text variant="secondary">No dividend announcements available.</Text>
              </Card>
            )
          }
        />
      </SafeAreaView>
    </GlassScreen>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    header: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 },
    backBtn: { minWidth: 44, minHeight: 44, alignItems: "center", justifyContent: "center", marginLeft: -10 },
    list: { paddingHorizontal: 16, paddingBottom: 28, flexGrow: 1 },
    row: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 14, paddingHorizontal: 4, minHeight: 44, borderRadius: 8 },
    iconBox: { width: 36, height: 36, borderRadius: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, alignItems: "center", justifyContent: "center" },
    sep: { height: StyleSheet.hairlineWidth, backgroundColor: c.border },
    center: { alignItems: "center", gap: 10, paddingVertical: 28, marginTop: 8 },
  });
