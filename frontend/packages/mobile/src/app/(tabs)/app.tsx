// Dashboard (`/app`) — premium liquid-glass rebuild of the web `/app` route.
// Top ribbon (search / notifications / account) + greeting + action row
// (Explore PSX → market screen, Add Transaction/Holding/Alert) + AI rec + net
// worth + stat cards + portfolio area chart + spending donut + watchlist +
// savings goals. Always dark (glass system). Mirrors web
// features/dashboard/Dashboard.tsx, backed by the live API (React Query).
import { useRouter } from "expo-router";
import { useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from "react-native";
import Animated, { FadeIn, FadeInDown, FadeOut, ZoomIn } from "react-native-reanimated";
import { SafeAreaView } from "react-native-safe-area-context";

import { AreaChart } from "@/components/charts/AreaChart";
import { DonutChart } from "@/components/charts/DonutChart";
import { QuickAddSheets, type QuickAdd } from "@/components/dashboard/QuickAddSheets";
import { TopRibbon } from "@/components/dashboard/TopRibbon";
import { GlassButton, GlassPrimaryButton } from "@/components/glass/GlassButtons";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Change, Text } from "@/components/ui";
import { Segmented } from "@/components/ui/controls";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/hooks/use-theme";
import { useFinanceGoals, useFinanceSummary } from "@/hooks/queries/use-finance";
import { useSpendingByCategory } from "@/hooks/queries/use-finance-series";
import { usePsxIndexCards } from "@/hooks/queries/use-market";
import { usePortfolioHistory, usePortfolioNetworth } from "@/hooks/queries/use-portfolio";
import { useEnrichedWatchlist, useRemoveFromWatchlist } from "@/hooks/queries/use-watchlist";
import { fmtNum, fmtPKR } from "@nafaiq/shared";
import { ArrowUpRight, iconFor, Plus, TrendingUp, X } from "@/lib/icons";
import { AiReportSheet } from "@/components/ai/AiReportSheet";
import { useDashboardRecommendation } from "@/hooks/ai/use-dashboard-recommendation";
import { useLang } from "@/hooks/use-lang";

// Backend bounds /api/portfolio/history days to [7, 365] — same map as web.
const RANGES: Record<string, number> = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365 };

type PeekData = { label: string; value: string; sub: string; subColor?: string; x: number; y: number };

function pctLabel(v: number) {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

/** "+PKR 2,500" / "-PKR 1,200" — matches web formatSignedPKR intent. */
function signedPKR(n: number) {
  return `${n >= 0 ? "+" : "-"}${fmtPKR(Math.abs(n))}`;
}

export default function Dashboard() {
  const { profile, user } = useAuth();
  const signedIn = !!user;
  const { colors } = useTheme();
  const { t } = useLang();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const { width } = useWindowDimensions();
  const chartW = width - 64;

  const firstName = (profile?.display_name || user?.email?.split("@")[0] || "Investor").split(" ")[0];
  const today = useMemo(
    () => new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    [],
  );

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

  /* Live data — same feeds as web Dashboard.tsx (real-user path). */
  const { data: indexCards } = usePsxIndexCards();
  const { data: networth, isLoading: networthLoading } = usePortfolioNetworth(signedIn);
  const historyQuery = usePortfolioHistory(RANGES[range] ?? 180, signedIn);
  const { data: financeSummary } = useFinanceSummary(undefined, signedIn);
  const { data: spendingByCat, isLoading: spendingLoading } = useSpendingByCategory(30, signedIn);
  const { data: userGoals, isLoading: goalsLoading } = useFinanceGoals(signedIn);
  const { data: watchlist, isLoading: watchlistLoading } = useEnrichedWatchlist(signedIn);
  const removeFromWatchlist = useRemoveFromWatchlist();

  const kse100ChangePct = indexCards?.find((c) => c.code === "KSE100")?.change_pct ?? null;
  const kse100Label = kse100ChangePct == null ? "--" : pctLabel(kse100ChangePct);
  const kse100Color =
    kse100ChangePct == null ? colors.textMuted : kse100ChangePct >= 0 ? colors.bull : colors.bear;

  const points = useMemo(() => historyQuery.data?.points ?? [], [historyQuery.data]);
  const portfolioSeries = useMemo(() => points.map((p) => p.value ?? 0), [points]);
  const benchmark = useMemo(() => points.map((p) => p.benchmark ?? 0), [points]);

  // KPI values — web Dashboard.tsx real-user mappings.
  const netWorth = networth?.total_market_value ?? 0;
  const todayPnl = networth?.today_pnl ?? 0;
  const todayPnlPct = networth?.today_pnl_pct ?? 0;
  const unrealizedPct = networth?.total_unrealized_pnl_pct ?? 0;
  const monthlySpending = financeSummary?.expenses ?? 0;
  const spendingDeltaPct =
    financeSummary && financeSummary.last_month_expense > 0
      ? Math.round(
          ((financeSummary.expenses - financeSummary.last_month_expense) /
            financeSummary.last_month_expense) *
            100,
        )
      : 0;
  const hasNoHoldings = signedIn && !!networth && networth.holding_count === 0;

  const donut = useMemo(
    () =>
      (spendingByCat?.categories ?? []).slice(0, 5).map((c, i) => ({
        label: c.category,
        value: c.pct,
        color: colors.chart[i % colors.chart.length],
      })),
    [spendingByCat, colors.chart],
  );

  const goals = (userGoals ?? []).slice(0, 3);
  const watch = watchlist ?? [];
  // Daily AI nudge — verified, cited, over the user's full finance picture.
  // Auto-loads today's cached row (free); refresh regenerates (costs quota).
  const dashRec = useDashboardRecommendation(signedIn);

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
              {today} · KSE-100 <Text style={{ color: kse100Color, fontWeight: "700" }}>{kse100Label}</Text> today
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

          {hasNoHoldings ? (
            /* First-run welcome — mirrors web's holding_count === 0 card. */
            <GlassCard style={[styles.card, { alignItems: "center", gap: 8 }]}>
              <Text variant="title" style={{ fontSize: 17 }}>Welcome to NafaIQ!</Text>
              <Text variant="secondary" style={{ textAlign: "center", lineHeight: 20 }}>
                Add your first holding, transaction, or goal to get started with real insights.
              </Text>
              <View style={{ flexDirection: "row", gap: 10, marginTop: 6 }}>
                <GlassPrimaryButton label="Add Holding" compact onPress={() => setQuickAdd("holding")} />
                <GlassButton label="Add Transaction" compact onPress={() => setQuickAdd("tx")} />
              </View>
            </GlassCard>
          ) : (
            <>
              {/* Net worth */}
              <GlassCard style={styles.card}>
                <Text variant="muted">Total Net Worth</Text>
                {networthLoading && signedIn ? (
                  <ActivityIndicator color={colors.primary} style={{ marginVertical: 14 }} accessibilityLabel="Loading net worth" />
                ) : (
                  <>
                    <Text style={styles.netWorth}>{fmtPKR(netWorth)}</Text>
                    <Text
                      style={{
                        color: todayPnl >= 0 ? colors.bull : colors.bear,
                        fontFamily: fonts.mono,
                        fontSize: 13,
                        marginTop: 4,
                      }}
                    >
                      {signedPKR(Math.round(todayPnl))} ({pctLabel(todayPnlPct)}) today
                    </Text>
                  </>
                )}
              </GlassCard>

              {/* Stat cards */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statRow}>
                <GlassStat
                  label="Portfolio Value"
                  value={fmtPKR(netWorth)}
                  sub={`${pctLabel(unrealizedPct)} all time`}
                  subColor={unrealizedPct >= 0 ? colors.bull : colors.bear}
                  onPeek={setPeek}
                  onPeekEnd={() => setPeek(null)}
                />
                <GlassStat
                  label="Monthly Spending"
                  value={fmtPKR(monthlySpending)}
                  sub={`${spendingDeltaPct >= 0 ? "+" : ""}${spendingDeltaPct}% vs last month`}
                  subColor={spendingDeltaPct > 0 ? colors.bear : colors.bull}
                  onPeek={setPeek}
                  onPeekEnd={() => setPeek(null)}
                />
                <GlassStat
                  label="Today's PSX P/L"
                  value={`${todayPnl >= 0 ? "+" : "-"}${fmtNum(Math.abs(Math.round(todayPnl)), 0)}`}
                  sub={pctLabel(todayPnlPct)}
                  subColor={todayPnl >= 0 ? colors.bull : colors.bear}
                  onPeek={setPeek}
                  onPeekEnd={() => setPeek(null)}
                />
              </ScrollView>
            </>
          )}

          {/* Portfolio value chart */}
          <GlassCard style={styles.card}>
            <View style={styles.between}>
              <Text variant="title" style={{ fontSize: 15 }}>Portfolio Value</Text>
              <View style={{ width: 150 }}>
                <Segmented options={Object.keys(RANGES)} value={range} onChange={setRange} />
              </View>
            </View>
            {historyQuery.isLoading && signedIn ? (
              <View style={styles.chartState}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading portfolio history" />
              </View>
            ) : historyQuery.isError ? (
              <View style={styles.chartState}>
                <Text variant="secondary">Could not load portfolio history.</Text>
                <GlassButton label="Retry" compact onPress={() => historyQuery.refetch()} />
              </View>
            ) : portfolioSeries.length === 0 ? (
              <View style={styles.chartState}>
                <Text variant="secondary" style={{ textAlign: "center" }}>
                  No portfolio history yet. Add holdings to build your chart.
                </Text>
              </View>
            ) : (
              <>
                <AreaChart data={portfolioSeries} benchmark={benchmark} width={chartW} />
                <View style={{ flexDirection: "row", gap: 16, marginTop: 6 }}>
                  <Legend color={colors.primary} label="Portfolio" />
                  <Legend color={colors.textMuted} label="KSE-100" />
                </View>
              </>
            )}
          </GlassCard>

          {/* AI recommendation of the day — verified, cited nudge over full finances */}
          {signedIn && (
            <AiReportSheet
              title={t("AI recommendation for today")}
              subtitle={dashRec.data?.content?.headline}
              variant="nudge"
              report={dashRec.data?.content}
              isLoading={dashRec.isLoading}
              error={dashRec.error}
              loadingLabel={t("Preparing your daily insight…")}
              emptyLabel={t("Tap for today's AI insight")}
              onRefresh={() => dashRec.refresh()}
              isRefreshing={dashRec.isRefreshing}
              refreshError={dashRec.refreshError}
            />
          )}

          {/* Spending breakdown */}
          <GlassCard style={styles.card}>
            <Text variant="title" style={{ fontSize: 16 }}>Spending Breakdown</Text>
            {spendingLoading && signedIn ? (
              <View style={styles.chartState}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading spending breakdown" />
              </View>
            ) : donut.length === 0 ? (
              <View style={styles.chartState}>
                <Text variant="secondary" style={{ textAlign: "center" }}>
                  No spending data yet. Add transactions to see your breakdown.
                </Text>
              </View>
            ) : (
              <>
                <View style={{ alignItems: "center", marginVertical: 6 }}>
                  <DonutChart
                    segments={donut}
                    size={156}
                    strokeWidth={24}
                    centerLabel={Math.round(spendingByCat?.total ?? 0).toLocaleString()}
                    centerSub="PKR total"
                  />
                </View>
                <View style={styles.legendGrid}>
                  {donut.map((s) => (
                    <View key={s.label} style={styles.legendRow}>
                      <View style={[styles.swatch, { backgroundColor: s.color }]} />
                      <Text variant="secondary" style={{ flex: 1, fontSize: 12.5 }} numberOfLines={1}>{s.label}</Text>
                      <Text style={{ fontFamily: fonts.mono, fontSize: 12.5, color: colors.textSecondary }}>{s.value}%</Text>
                    </View>
                  ))}
                </View>
              </>
            )}
          </GlassCard>

          {/* Watchlist */}
          <GlassCard style={styles.card}>
            <View style={styles.between}>
              <Text variant="title" style={{ fontSize: 16 }}>Watchlist</Text>
              <Pressable onPress={() => router.push("/watchlist" as never)} hitSlop={8} accessibilityRole="button" accessibilityLabel="Open watchlist">
                <Text style={{ color: colors.primary, fontWeight: "600", fontSize: 13 }}>View all</Text>
              </Pressable>
            </View>
            {watchlistLoading && signedIn ? (
              <View style={styles.chartState}>
                <ActivityIndicator color={colors.primary} accessibilityLabel="Loading watchlist" />
              </View>
            ) : watch.length === 0 ? (
              <Text variant="secondary" style={{ paddingVertical: 10 }}>
                Your watchlist is empty. Add stocks from the PSX page to track them here.
              </Text>
            ) : (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingTop: 4 }}>
                {watch.map((s) => {
                  const hasPrice = s.price != null && s.price > 0;
                  const changePct = s.change_pct ?? 0;
                  return (
                    <Pressable key={s.symbol} onPress={() => router.push(`/stock/${s.symbol}`)} accessibilityRole="button" accessibilityLabel={`${s.symbol} ${s.company_name}`}>
                      <GlassCard radius={16} intensity={18} style={styles.watchCard}>
                        <View style={styles.between}>
                          <Text style={{ fontWeight: "800", fontSize: 14 }}>{s.symbol}</Text>
                          <Pressable
                            onPress={() => {
                              removeFromWatchlist.mutate(s.symbol);
                              showToast(`${s.symbol} removed from watchlist`);
                            }}
                            hitSlop={14}
                            accessibilityRole="button"
                            accessibilityLabel={`Remove ${s.symbol} from watchlist`}
                          >
                            <X color={colors.textMuted} size={14} />
                          </Pressable>
                        </View>
                        <Text variant="muted" numberOfLines={1}>{s.company_name}</Text>
                        <Text style={{ fontFamily: fonts.mono, fontSize: 16, marginTop: 2 }}>
                          {hasPrice ? fmtNum(s.price as number) : "—"}
                        </Text>
                        <View style={{ marginTop: 6 }}>
                          {hasPrice ? (
                            <Change pct={changePct} />
                          ) : (
                            <Text variant="muted">Price unavailable</Text>
                          )}
                        </View>
                      </GlassCard>
                    </Pressable>
                  );
                })}
              </ScrollView>
            )}
          </GlassCard>

          {/* Savings goals */}
          <GlassCard style={styles.card}>
            <Text variant="title" style={{ fontSize: 16 }}>Savings Goals</Text>
            {goalsLoading && signedIn ? (
              <ActivityIndicator color={colors.primary} style={{ marginVertical: 14 }} accessibilityLabel="Loading savings goals" />
            ) : goals.length === 0 ? (
              <Text variant="secondary" style={{ paddingVertical: 10 }}>
                No savings goals yet. Add a goal from Finance to track progress here.
              </Text>
            ) : (
              goals.map((g) => {
                const pct = g.target > 0 ? g.saved / g.target : 0;
                const c = g.color === "warning" ? colors.gold : colors.bull;
                const Icon = iconFor(g.emoji ?? "");
                return (
                  <View key={g.id} style={{ gap: 6, marginTop: 8 }}>
                    <View style={styles.goalHead}>
                      <View style={[styles.goalIcon, { backgroundColor: c + "1f" }]}>
                        <Icon color={c} size={16} />
                      </View>
                      <Text style={{ flex: 1, fontWeight: "600", fontSize: 13.5 }}>{g.name}</Text>
                      <Text style={{ color: c, fontFamily: fonts.mono, fontSize: 13 }}>{Math.round(pct * 100)}%</Text>
                    </View>
                    <ProgressBar value={pct} color={c} />
                    <Text variant="muted">{fmtPKR(g.saved)} of {fmtPKR(g.target)}</Text>
                    {g.ai_tip ? <Text variant="muted" style={{ fontStyle: "italic" }}>{g.ai_tip}</Text> : null}
                  </View>
                );
              })
            )}
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
                <Text style={{ color: peek.subColor ?? colors.bull, fontFamily: fonts.mono, fontSize: 13, marginTop: 4 }}>{peek.sub}</Text>
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
  subColor,
  onPeek,
  onPeekEnd,
}: {
  label: string;
  value: string;
  sub: string;
  subColor?: string;
  onPeek: (p: PeekData) => void;
  onPeekEnd: () => void;
}) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const ref = useRef<View>(null);
  function peek() {
    ref.current?.measureInWindow((x, y) => onPeek({ label, value, sub, subColor, x, y }));
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
        <Text style={{ color: subColor ?? colors.bull, fontFamily: fonts.mono, fontSize: 12, marginTop: 4 }}>{sub}</Text>
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


    netWorth: { fontFamily: fonts.mono, fontSize: 32, fontWeight: "700", color: c.textPrimary, marginTop: 4, letterSpacing: -0.5 },

    statRow: { gap: 12, paddingVertical: 2, paddingRight: 8 },
    statCard: { width: 158, padding: 14 },

    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },

    chartState: { minHeight: 120, alignItems: "center", justifyContent: "center", gap: 10, paddingVertical: 12 },

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
