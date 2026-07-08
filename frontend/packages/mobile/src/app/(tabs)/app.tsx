// Dashboard (`/app`) — premium liquid-glass rebuild of the web `/app` route.
// Top ribbon (search / notifications / account) + greeting + action row
// (Explore PSX → market screen, Add Transaction/Holding/Alert) + AI rec + net
// worth + stat cards + portfolio area chart + spending donut + watchlist +
// savings goals. Always dark (glass system). Mirrors zenith-main:src/routes/app.tsx.
import { useRouter } from "expo-router";
import { useMemo, useRef, useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from "react-native";
import Animated, { FadeIn, FadeInDown, FadeOut, ZoomIn } from "react-native-reanimated";
import { SafeAreaView } from "react-native-safe-area-context";

import { AreaChart } from "@/components/charts/AreaChart";
import { DonutChart } from "@/components/charts/DonutChart";
import { Sparkline } from "@/components/charts/Sparkline";
import { QuickAddSheets, type QuickAdd } from "@/components/dashboard/QuickAddSheets";
import { TopRibbon } from "@/components/dashboard/TopRibbon";
import { GlassButton, GlassPrimaryButton } from "@/components/glass/GlassButtons";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Change, SignalBadge, Text } from "@/components/ui";
import { Segmented } from "@/components/ui/controls";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/hooks/use-theme";
import { useFinanceStore } from "@/hooks/use-finance-store";
import { fmtNum, fmtPKR, generateOHLCV, INDICES, STOCKS, WATCHLIST } from "@nafaiq/shared";
import { SPENDING } from "@nafaiq/shared";
import { ArrowUpRight, iconFor, Plus, Sparkles, TrendingUp } from "@/lib/icons";

const RANGES: Record<string, number> = { "1M": 30, "3M": 90, "6M": 180, "1Y": 260 };

type PeekData = { label: string; value: string; sub: string; x: number; y: number };

export default function Dashboard() {
  const { profile, user } = useAuth();
  const { goals } = useFinanceStore();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const { width } = useWindowDimensions();
  const chartW = width - 64;

  const firstName = (profile?.display_name || user?.email?.split("@")[0] || "Investor").split(" ")[0];
  const today = useMemo(
    () => new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    [],
  );

  const [showAI, setShowAI] = useState(true);
  const [range, setRange] = useState("6M");
  const [quickAdd, setQuickAdd] = useState<QuickAdd>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [peek, setPeek] = useState<PeekData | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
  }

  const portfolioSeries = useMemo(() => generateOHLCV(7, 761190, 858054, RANGES[range]).map((c) => c.close), [range]);
  const benchmark = useMemo(
    () => generateOHLCV(1, INDICES[0].start, INDICES[0].end, RANGES[range]).map((c) => c.close),
    [range],
  );
  const watch = useMemo(
    () =>
      WATCHLIST.map((tk) => {
        const s = STOCKS[tk];
        return { ...s, series: generateOHLCV(s.seed, s.start, s.price, 7).map((c) => c.close) };
      }),
    [],
  );
  const donut = useMemo(() => SPENDING.map((s) => ({ label: s.name, value: s.value, color: s.color })), []);

  return (
    <GlassScreen>
      <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
        <View style={styles.ribbon}>
          <TopRibbon />
        </View>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {/* Greeting */}
          <View>
            <Text variant="display" style={{ fontSize: 24, fontFamily: Platform.select({ ios: "Avenir-Heavy", default: fonts.sans }) }}>
              Asalam-o-Alaikum, {firstName}
            </Text>
            <Text variant="secondary" style={{ marginTop: 4 }}>
              {today} · KSE-100 <Text style={{ color: colors.bull, fontWeight: "700" }}>+1.24%</Text> today
            </Text>
          </View>

          {/* Action row */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.actions}>
            <GlassPrimaryButton
              label="Explore PSX"
              icon={<TrendingUp color={colors.primaryForeground} size={16} />}
              onPress={() => router.push("/(tabs)/psx")}
            />
            <GlassButton label="Add Transaction" icon={<Plus color={colors.textPrimary} size={15} />} onPress={() => setQuickAdd("tx")} />
            <GlassButton label="Add Holding" icon={<Plus color={colors.textPrimary} size={15} />} onPress={() => setQuickAdd("holding")} />
            <GlassButton label="Add Alert" icon={<Plus color={colors.textPrimary} size={15} />} onPress={() => setQuickAdd("alert")} />
          </ScrollView>

          {/* Net worth */}
          <GlassCard style={styles.card}>
            <Text variant="muted">Total Net Worth</Text>
            <Text style={styles.netWorth}>{fmtPKR(4280500)}</Text>
            <Text style={{ color: colors.bull, fontFamily: fonts.mono, fontSize: 13, marginTop: 4 }}>
              +PKR 56,000 (+1.32%) this month
            </Text>
          </GlassCard>

          {/* Stat cards */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statRow}>
            <GlassStat label="Portfolio Value" value={fmtPKR(858054)} sub="+12.73% YTD" onPeek={setPeek} onPeekEnd={() => setPeek(null)} />
            <GlassStat label="Monthly Spending" value={fmtPKR(112050)} sub="-12% vs May" onPeek={setPeek} onPeekEnd={() => setPeek(null)} />
            <GlassStat label="Today's PSX P/L" value={`+${fmtNum(17480, 0)}`} sub="+1.42%" onPeek={setPeek} onPeekEnd={() => setPeek(null)} />
          </ScrollView>

          {/* Portfolio value chart */}
          <GlassCard style={styles.card}>
            <View style={styles.between}>
              <Text variant="title" style={{ fontSize: 15 }}>Portfolio Value</Text>
              <View style={{ width: 150 }}>
                <Segmented options={Object.keys(RANGES)} value={range} onChange={setRange} />
              </View>
            </View>
            <AreaChart data={portfolioSeries} benchmark={benchmark} width={chartW} />
            <View style={{ flexDirection: "row", gap: 16, marginTop: 6 }}>
              <Legend color={colors.primary} label="Portfolio" />
              <Legend color={colors.textMuted} label="KSE-100" />
            </View>
          </GlassCard>

          {/* AI Recommendation — below the graph */}
          {showAI && (
            <Animated.View exiting={FadeOut}>
              <GlassCard style={[styles.card, { borderColor: colors.ai + "44" }]}>
                <View style={styles.aiHead}>
                  <View style={styles.aiIcon}>
                    <Sparkles color={colors.ai} size={18} />
                  </View>
                  <Text style={{ color: colors.ai, fontWeight: "700", fontSize: 14 }}>AI Recommendation</Text>
                  <View style={styles.confPill}>
                    <Text style={{ color: colors.ai, fontSize: 11, fontWeight: "700" }}>92% confidence</Text>
                  </View>
                </View>
                <Text style={{ fontWeight: "700", fontSize: 15, marginTop: 4 }}>
                  Redirect PKR 5,000 from dining to your Hajj Fund.
                </Text>
                <Text variant="secondary" style={{ marginTop: 4, lineHeight: 20 }}>
                  You spent 15% more on dining this month — reallocating brings your goal 3 months closer. HBL is also
                  flashing a Strong Buy, up 2.41% on rising volume.
                </Text>
                <View style={{ flexDirection: "row", gap: 10, marginTop: 12 }}>
                  <GlassPrimaryButton label="View" compact onPress={() => router.push("/(tabs)/psx")} style={{ paddingHorizontal: 22 }} />
                  <GlassButton label="Dismiss" compact onPress={() => setShowAI(false)} />
                </View>
              </GlassCard>
            </Animated.View>
          )}

          {/* Spending breakdown */}
          <GlassCard style={styles.card}>
            <Text variant="title" style={{ fontSize: 16 }}>Spending Breakdown</Text>
            <View style={{ alignItems: "center", marginVertical: 6 }}>
              <DonutChart segments={donut} size={156} strokeWidth={24} centerLabel="132,000" centerSub="PKR total" />
            </View>
            <View style={styles.legendGrid}>
              {SPENDING.map((s) => (
                <View key={s.name} style={styles.legendRow}>
                  <View style={[styles.swatch, { backgroundColor: s.color }]} />
                  <Text variant="secondary" style={{ flex: 1, fontSize: 12.5 }} numberOfLines={1}>{s.name}</Text>
                  <Text style={{ fontFamily: fonts.mono, fontSize: 12.5, color: colors.textSecondary }}>{s.value}%</Text>
                </View>
              ))}
            </View>
          </GlassCard>

          {/* Watchlist */}
          <GlassCard style={styles.card}>
            <View style={styles.between}>
              <Text variant="title" style={{ fontSize: 16 }}>Watchlist</Text>
              <Pressable onPress={() => router.push("/(tabs)/psx")} hitSlop={8} accessibilityRole="button" accessibilityLabel="View all on PSX">
                <Text style={{ color: colors.primary, fontWeight: "600", fontSize: 13 }}>View all</Text>
              </Pressable>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingTop: 4 }}>
              {watch.map((s) => (
                <Pressable key={s.ticker} onPress={() => router.push(`/stock/${s.ticker}`)} accessibilityRole="button" accessibilityLabel={`${s.ticker} ${s.name}`}>
                  <GlassCard radius={16} intensity={18} style={styles.watchCard}>
                    <View style={styles.between}>
                      <Text style={{ fontWeight: "800", fontSize: 14 }}>{s.ticker}</Text>
                      <Change pct={s.changePct} />
                    </View>
                    <Text variant="muted" numberOfLines={1}>{s.name}</Text>
                    <Text style={{ fontFamily: fonts.mono, fontSize: 16, marginTop: 2 }}>{fmtNum(s.price)}</Text>
                    <View style={{ marginTop: 6 }}>
                      <Sparkline data={s.series} width={126} height={30} />
                    </View>
                    <View style={{ marginTop: 6 }}>
                      <SignalBadge signal={s.signal} />
                    </View>
                  </GlassCard>
                </Pressable>
              ))}
            </ScrollView>
          </GlassCard>

          {/* Savings goals */}
          <GlassCard style={styles.card}>
            <Text variant="title" style={{ fontSize: 16 }}>Savings Goals</Text>
            {goals.slice(0, 3).map((g) => {
              const pct = g.saved / g.target;
              const c = g.color === "warning" ? colors.gold : colors.bull;
              const Icon = iconFor(g.emoji);
              return (
                <View key={g.name} style={{ gap: 6, marginTop: 8 }}>
                  <View style={styles.goalHead}>
                    <View style={[styles.goalIcon, { backgroundColor: c + "1f" }]}>
                      <Icon color={c} size={16} />
                    </View>
                    <Text style={{ flex: 1, fontWeight: "600", fontSize: 13.5 }}>{g.name}</Text>
                    <Text style={{ color: c, fontFamily: fonts.mono, fontSize: 13 }}>{Math.round(pct * 100)}%</Text>
                  </View>
                  <ProgressBar value={pct} color={c} />
                  <Text variant="muted">{fmtPKR(g.saved)} of {fmtPKR(g.target)}</Text>
                  {g.ai ? <Text variant="muted" style={{ fontStyle: "italic" }}>{g.ai}</Text> : null}
                </View>
              );
            })}
          </GlassCard>
        </ScrollView>

        {/* Quick-add sheets */}
        <QuickAddSheets which={quickAdd} onClose={() => setQuickAdd(null)} onToast={showToast} />

        {/* Toast */}
        {toast && (
          <Animated.View entering={FadeInDown} exiting={FadeOut} style={styles.toastWrap} pointerEvents="none">
            <GlassCard radius={999} intensity={40} style={styles.toast}>
              <ArrowUpRight color={colors.primary} size={15} />
              <Text style={{ fontWeight: "600", fontSize: 13 }}>{toast}</Text>
            </GlassCard>
          </Animated.View>
        )}

        {/* KPI peek — long-press a stat card to enlarge it in place. */}
        {peek && (
          <>
            <Animated.View entering={FadeIn.duration(120)} exiting={FadeOut} style={styles.peekScrim} pointerEvents="none" />
            <Animated.View
              entering={ZoomIn.duration(170)}
              pointerEvents="none"
              style={[styles.peekCard, { top: peek.y, left: Math.max(12, Math.min(peek.x, width - 252)) }]}
            >
              <GlassCard radius={18} intensity={48} sheen={0.2} style={styles.peekInner}>
                <View style={[StyleSheet.absoluteFill, { backgroundColor: "rgba(9,14,28,0.6)" }]} pointerEvents="none" />
                <Text variant="muted">{peek.label}</Text>
                <Text style={styles.peekValue}>{peek.value}</Text>
                <Text style={{ color: colors.bull, fontFamily: fonts.mono, fontSize: 13, marginTop: 4 }}>{peek.sub}</Text>
              </GlassCard>
            </Animated.View>
          </>
        )}
      </SafeAreaView>
    </GlassScreen>
  );
}

function GlassStat({
  label,
  value,
  sub,
  onPeek,
  onPeekEnd,
}: {
  label: string;
  value: string;
  sub: string;
  onPeek: (p: PeekData) => void;
  onPeekEnd: () => void;
}) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const ref = useRef<View>(null);
  function peek() {
    ref.current?.measureInWindow((x, y) => onPeek({ label, value, sub, x, y }));
  }
  return (
    <Pressable
      ref={ref}
      onLongPress={peek}
      onPressOut={onPeekEnd}
      delayLongPress={220}
      accessibilityRole="button"
      accessibilityLabel={`${label}: ${value}, ${sub}. Long press to enlarge.`}
    >
      <GlassCard radius={18} intensity={20} style={styles.statCard}>
        <Text variant="muted" numberOfLines={1}>{label}</Text>
        <Text style={{ fontFamily: fonts.mono, fontSize: 18, marginTop: 6 }} numberOfLines={1}>{value}</Text>
        <Text style={{ color: colors.bull, fontFamily: fonts.mono, fontSize: 12, marginTop: 4 }}>{sub}</Text>
      </GlassCard>
    </Pressable>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <View style={{ width: 14, height: 3, borderRadius: 2, backgroundColor: color }} />
      <Text variant="muted">{label}</Text>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    ribbon: { paddingHorizontal: 16, paddingTop: 6, paddingBottom: 8, zIndex: 30, elevation: 30 },
    content: { paddingHorizontal: 16, paddingBottom: 28, gap: 16 },
    actions: { gap: 10, paddingVertical: 2, paddingRight: 8 },

    card: { padding: 16, gap: 4 },

    aiHead: { flexDirection: "row", alignItems: "center", gap: 8 },
    aiIcon: { width: 34, height: 34, borderRadius: 12, backgroundColor: c.ai + "1f", alignItems: "center", justifyContent: "center" },
    confPill: { backgroundColor: c.ai + "1a", borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },

    netWorth: { fontFamily: fonts.mono, fontSize: 32, fontWeight: "700", color: c.textPrimary, marginTop: 4, letterSpacing: -0.5 },

    statRow: { gap: 12, paddingVertical: 2, paddingRight: 8 },
    statCard: { width: 158, padding: 14 },

    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },

    legendGrid: { flexDirection: "row", flexWrap: "wrap", marginTop: 4 },
    legendRow: { flexDirection: "row", alignItems: "center", gap: 8, width: "50%", paddingVertical: 4, paddingRight: 8 },
    swatch: { width: 10, height: 10, borderRadius: 3 },

    watchCard: { width: 150, padding: 12, gap: 2 },

    goalHead: { flexDirection: "row", alignItems: "center", gap: 10 },
    goalIcon: { width: 30, height: 30, borderRadius: 10, alignItems: "center", justifyContent: "center" },

    toastWrap: { position: "absolute", left: 0, right: 0, bottom: 24, alignItems: "center" },
    toast: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingVertical: 10 },

    peekScrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.32)" },
    peekCard: { position: "absolute", width: 240, zIndex: 60, elevation: 24 },
    peekInner: {
      padding: 16,
      borderColor: c.primary + "66",
      shadowColor: c.primary,
      shadowOpacity: 0.3,
      shadowRadius: 16,
      shadowOffset: { width: 0, height: 6 },
    },
    peekValue: { fontFamily: fonts.mono, fontSize: 23, fontWeight: "700", color: c.textPrimary, marginTop: 6, letterSpacing: -0.3 },
  });
