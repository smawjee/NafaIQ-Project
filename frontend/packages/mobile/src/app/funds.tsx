// Mutual Funds (`/funds`): virtualized list of MUFAP funds from GET /api/funds
// via useFunds(). Category filter chips narrow the list. Shows fund name,
// category/AMC, and latest NAV (PKR). Mirrors web features/funds MutualFundsTab.
import { Stack, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Platform, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Card, Text } from "@/components/ui";
import { ChipRow } from "@/components/ui/controls";
import { fonts, type ThemeColors } from "@/constants/theme";
import { type Fund, useFunds } from "@/hooks/queries/use-funds";
import { useTheme } from "@/hooks/use-theme";
import { ArrowLeft, Landmark } from "@/lib/icons";
import { fmtPKR } from "@nafaiq/shared";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });
const ALL = "All";

export default function FundsScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const [category, setCategory] = useState(ALL);
  // Fetch all funds once; filter client-side so switching chips is instant.
  const { data, isPending, isError, refetch } = useFunds();
  const funds = useMemo(() => data ?? [], [data]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const f of funds) if (f.category) set.add(f.category);
    return [ALL, ...Array.from(set).sort()];
  }, [funds]);

  const filtered = useMemo(
    () => (category === ALL ? funds : funds.filter((f) => f.category === category)),
    [funds, category],
  );

  const renderItem = useCallback(
    ({ item }: { item: Fund }) => {
      const amc = typeof item.amc === "string" ? item.amc : null;
      const meta = [item.category, amc].filter(Boolean).join(" · ");
      return (
        <Pressable onPress={() => router.push(`/fund/${encodeURIComponent(item.fund_code)}` as never)} accessibilityRole="button" accessibilityLabel={`Open ${item.name} NAV history`}>
        <Card style={styles.row}>
          <View style={styles.iconBox}>
            <Landmark color={colors.primary} size={16} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: "600" }} numberOfLines={2}>
              {item.name}
            </Text>
            {meta ? <Text variant="muted">{meta}</Text> : null}
          </View>
          <View style={styles.navCol}>
            <Text variant="mono" style={{ fontSize: 13.5 }}>
              {item.latest_nav != null ? fmtPKR(item.latest_nav, 2) : "—"}
            </Text>
            <Text variant="muted" style={{ marginTop: 2 }}>
              NAV
            </Text>
          </View>
        </Card>
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
            Mutual Funds
          </Text>
        </View>

        {categories.length > 1 ? (
          <View style={styles.chips}>
            <ChipRow options={categories} value={category} onChange={setCategory} />
          </View>
        ) : null}

        <FlatList
          data={isPending ? [] : filtered}
          keyExtractor={(f) => f.fund_code}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            isPending ? (
              <Card style={styles.center}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading funds" />
              </Card>
            ) : isError ? (
              <Card style={styles.center}>
                <Text variant="secondary">Could not load funds.</Text>
                <Button title="Retry" variant="outline" onPress={() => refetch()} />
              </Card>
            ) : (
              <Card style={styles.center}>
                <Text variant="secondary">
                  {category === ALL ? "No mutual funds available." : "No funds in this category."}
                </Text>
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
    chips: { paddingHorizontal: 16, paddingBottom: 8 },
    list: { paddingHorizontal: 16, paddingBottom: 28, gap: 8, flexGrow: 1 },
    row: { flexDirection: "row", alignItems: "center", gap: 12, padding: 14 },
    iconBox: { width: 36, height: 36, borderRadius: 8, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, alignItems: "center", justifyContent: "center" },
    navCol: { alignItems: "flex-end", minWidth: 92 },
    center: { alignItems: "center", gap: 10, paddingVertical: 28, marginTop: 8 },
  });
