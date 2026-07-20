// More hub (`/more`): a pushed route linking out to the market-data screens
// (News, Mutual Funds, Dividends) plus an inline Macro snapshot card
// (policy rate + USD/PKR FX + key SBP rates). Reached via router.push("/more")
// from the PSX tab. Mirrors the web app's macro/reference surfaces.
import { Stack, useRouter } from "expo-router";
import { useMemo } from "react";
import { ActivityIndicator, Platform, Pressable, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassScreen } from "@/components/glass/GlassScreen";
import { Card, Text } from "@/components/ui";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import { useMacroFx, useMacroRates, usePolicyRate } from "@/hooks/queries/use-macro";
import { useTheme } from "@/hooks/use-theme";
import {
  ArrowLeft,
  Banknote,
  ChevronRight,
  Coins,
  Landmark,
  type LucideIcon,
  Newspaper,
  Percent,
} from "@/lib/icons";
import { fmtNum } from "@nafaiq/shared";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

const LINKS: { label: string; desc: string; icon: LucideIcon; href: string }[] = [
  { label: "Market News", desc: "Latest PSX headlines", icon: Newspaper, href: "/news" },
  { label: "Mutual Funds", desc: "MUFAP funds & NAV", icon: Landmark, href: "/funds" },
  { label: "Dividends", desc: "Payouts & ex-dates", icon: Coins, href: "/dividends" },
];

export default function MoreScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const policy = usePolicyRate();
  const fx = useMacroFx();
  const rates = useMacroRates(undefined, 12);

  // USD/PKR from the FX table (selling preferred, else buying).
  const usd = useMemo(() => {
    const row = (fx.data ?? []).find((r) => (r.currency || "").toUpperCase().includes("USD"));
    if (!row) return null;
    return row.selling ?? row.buying ?? null;
  }, [fx.data]);

  // Latest value per rate series (rows arrive newest-ish; keep first seen).
  const keyRates = useMemo(() => {
    const seen = new Map<string, number>();
    for (const r of rates.data ?? []) {
      const key = r.series || "Rate";
      if (!seen.has(key) && typeof r.value === "number") seen.set(key, r.value);
    }
    return Array.from(seen.entries()).slice(0, 4);
  }, [rates.data]);

  const macroLoading = policy.isPending || fx.isPending || rates.isPending;
  const macroError = policy.isError && fx.isError && rates.isError;

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
            More
          </Text>
        </View>

        <View style={styles.content}>
          <View style={styles.group}>
            {LINKS.map((l, i) => {
              const Icon = l.icon;
              return (
                <Pressable
                  key={l.href}
                  onPress={() => router.push(l.href as never)}
                  accessibilityRole="button"
                  accessibilityLabel={`${l.label}. ${l.desc}`}
                  style={[
                    styles.row,
                    i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
                  ]}
                >
                  <View style={styles.iconBox}>
                    <Icon color={colors.primary} size={18} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontWeight: "600" }}>{l.label}</Text>
                    <Text variant="muted">{l.desc}</Text>
                  </View>
                  <ChevronRight color={colors.textMuted} size={18} />
                </Pressable>
              );
            })}
          </View>

          {/* Inline macro snapshot */}
          <Text variant="title">Macro Snapshot</Text>
          <Card style={{ gap: 14 }}>
            {macroLoading ? (
              <View style={styles.center}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading macro data" />
              </View>
            ) : macroError ? (
              <View style={styles.center}>
                <Text variant="muted">Could not load macro data.</Text>
              </View>
            ) : (
              <>
                <View style={styles.statGrid}>
                  <MacroStat
                    icon={Percent}
                    label="Policy Rate"
                    value={policy.data?.rate != null ? `${fmtNum(policy.data.rate, 2)}%` : "—"}
                    colors={colors}
                    styles={styles}
                  />
                  <MacroStat
                    icon={Banknote}
                    label="USD / PKR"
                    value={usd != null ? fmtNum(usd, 2) : "—"}
                    colors={colors}
                    styles={styles}
                  />
                </View>
                {keyRates.length > 0 ? (
                  <View style={{ gap: 8 }}>
                    <Text variant="muted">Key rates</Text>
                    {keyRates.map(([series, value]) => (
                      <View key={series} style={styles.rateRow}>
                        <Text variant="secondary" numberOfLines={1} style={{ flex: 1 }}>
                          {series}
                        </Text>
                        <Text variant="mono" style={{ fontSize: 13 }}>
                          {fmtNum(value, 2)}
                        </Text>
                      </View>
                    ))}
                  </View>
                ) : null}
              </>
            )}
          </Card>
        </View>
      </SafeAreaView>
    </GlassScreen>
  );
}

function MacroStat({
  icon: Icon,
  label,
  value,
  colors,
  styles,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  colors: ThemeColors;
  styles: ReturnType<typeof makeStyles>;
}) {
  return (
    <View style={styles.stat}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
        <Icon color={colors.textSecondary} size={14} />
        <Text variant="muted">{label}</Text>
      </View>
      <Text variant="mono" style={{ fontSize: 18, marginTop: 4 }}>
        {value}
      </Text>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    header: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 },
    backBtn: { minWidth: 44, minHeight: 44, alignItems: "center", justifyContent: "center", marginLeft: -10 },
    content: { padding: 16, paddingTop: 8, gap: 16 },
    group: { borderWidth: 1, borderColor: c.border, borderRadius: radii.card, backgroundColor: c.surface, overflow: "hidden" },
    row: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 14, paddingVertical: 14, minHeight: 64 },
    iconBox: { width: 40, height: 40, borderRadius: 10, borderWidth: 1, borderColor: c.border, backgroundColor: c.elevated, alignItems: "center", justifyContent: "center" },
    center: { alignItems: "center", justifyContent: "center", paddingVertical: 20 },
    statGrid: { flexDirection: "row", gap: 12 },
    stat: { flex: 1, borderWidth: 1, borderColor: c.border, borderRadius: 12, backgroundColor: c.elevated, padding: 12 },
    rateRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, minHeight: 32 },
  });
