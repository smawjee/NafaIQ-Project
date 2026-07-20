// Portfolio (`/portfolio`): live backend data — networth/value stat cards,
// /api/portfolio/performance chart vs KSE-100, /api/portfolio/allocation
// donut, and real holdings CRUD against /api/portfolio/:id/holdings.
// Mirrors web features/portfolio/Portfolio.tsx (auto-creates a "Main"
// portfolio on first add, like web).
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Platform, Pressable, StyleSheet, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AreaChart } from "@/components/charts/AreaChart";
import { DonutChart, type DonutSegment } from "@/components/charts/DonutChart";
import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { GlassSheet } from "@/components/glass/GlassSheet";
import { Field } from "@/components/Modal";
import { AiReportSheet } from "@/components/ai/AiReportSheet";
import { Button, Change, Text } from "@/components/ui";
import { Segmented } from "@/components/ui/controls";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import {
  useAddHolding,
  useCreatePortfolio,
  useCreateStockTransaction,
  usePortfolioAllocation,
  usePortfolioList,
  usePortfolioNetworth,
  usePortfolioPerformance,
  usePortfolioValue,
  useRemoveHolding,
  useStockTransactions,
  useUpdateHolding,
  type HoldingValue,
  type StockTransaction,
} from "@/hooks/queries/use-portfolio";
import { usePsxSymbols } from "@/hooks/queries/use-market";
import { usePortfolioReport } from "@/hooks/ai/use-ai-report";
import { useTheme } from "@/hooks/use-theme";
import { fmtPKR } from "@nafaiq/shared";
import { ArrowLeftRight, ArrowRight, Pencil, Plus, Trash2 } from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });
const AVENIR_MED = Platform.select({ ios: "Avenir-Medium", default: fonts.sans });
// Backend bounds /api/portfolio/performance days to [7, 365].
const RANGES: Record<string, number> = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365 };
const emptyForm = { ticker: "", shares: "", avgCost: "" };
const emptyTrade = { symbol: "", side: "buy" as "buy" | "sell", quantity: "", price: "" };

export default function PortfolioScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { width } = useWindowDimensions();
  const chartW = width - 64;
  const [range, setRange] = useState("6M");

  const { user } = useAuth();
  const isLoggedIn = !!user;

  const {
    data: portfolios,
    isLoading: portfoliosLoading,
    isError: portfoliosError,
    refetch: refetchPortfolios,
  } = usePortfolioList(isLoggedIn);
  const portfolioId = portfolios?.[0]?.id ?? null;
  const { data: portfolioValue, isLoading: valueLoading } = usePortfolioValue(
    portfolioId,
    isLoggedIn,
  );
  const { data: networth } = usePortfolioNetworth(isLoggedIn);
  const portfolioReport = usePortfolioReport(180);
  const { data: performance, isLoading: perfLoading } = usePortfolioPerformance(
    RANGES[range] ?? 180,
    isLoggedIn,
  );
  const { data: allocationData } = usePortfolioAllocation("sector", isLoggedIn);
  // Per-symbol sector labels from /api/symbols (web Portfolio.tsx sectorMap).
  const { data: symbols } = usePsxSymbols();
  const sectorMap = useMemo(
    () => new Map((symbols ?? []).map((s) => [s.symbol, s.sector ?? "Other"])),
    [symbols],
  );

  const addHoldingApi = useAddHolding(portfolioId);
  const updateHoldingApi = useUpdateHolding(portfolioId);
  const removeHoldingApi = useRemoveHolding(portfolioId);
  const createPortfolio = useCreatePortfolio();
  const createTxn = useCreateStockTransaction();
  const {
    data: transactions,
    isLoading: txnsLoading,
    isError: txnsError,
  } = useStockTransactions(100, isLoggedIn);

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [formErr, setFormErr] = useState("");
  const [tradeOpen, setTradeOpen] = useState(false);
  const [trade, setTrade] = useState(emptyTrade);
  const [tradeErr, setTradeErr] = useState("");

  const holdings: HoldingValue[] = portfolioValue?.holdings ?? [];
  const listLoading = portfoliosLoading || (!!portfolioId && valueLoading && !portfolioValue);

  // Stat card totals — /:id/value first, /networth as fallback (matches web).
  const totals = {
    value: portfolioValue?.totals.market_value ?? networth?.total_market_value ?? 0,
    invested: portfolioValue?.totals.cost_basis ?? networth?.total_cost_basis ?? 0,
    gain: portfolioValue?.totals.unrealized_pnl ?? networth?.total_unrealized_pnl ?? 0,
    gainPct: portfolioValue?.totals.pnl_pct ?? networth?.total_unrealized_pnl_pct ?? 0,
    today: networth?.today_pnl ?? 0,
    todayPct: networth?.today_pnl_pct ?? 0,
  };

  const perfPoints = useMemo(() => performance?.points ?? [], [performance]);
  const series = useMemo(() => perfPoints.map((p) => p.value ?? 0), [perfPoints]);
  const benchmark = useMemo(() => perfPoints.map((p) => p.benchmark ?? 0), [perfPoints]);

  const allocation = useMemo<(DonutSegment & { pct: number })[]>(
    () =>
      (allocationData?.items ?? []).map((it, i) => ({
        label: it.sector ?? it.symbol ?? "Other",
        value: it.value ?? 0,
        pct: it.pct ?? 0,
        color: colors.chart[i % colors.chart.length],
      })),
    [allocationData, colors.chart],
  );

  const saving =
    addHoldingApi.isPending || updateHoldingApi.isPending || createPortfolio.isPending;

  function openAdd() {
    setEditingId(null);
    setForm(emptyForm);
    setFormErr("");
    setFormOpen(true);
  }
  function openEdit(h: HoldingValue) {
    setEditingId(h.id);
    setForm({ ticker: h.symbol, shares: String(h.shares ?? ""), avgCost: String(h.avg_cost ?? "") });
    setFormErr("");
    setFormOpen(true);
  }
  function remove(h: HoldingValue) {
    removeHoldingApi.mutate(h.id);
  }
  function saveHolding() {
    setFormErr("");
    const shares = Number(form.shares);
    const avgCost = Number(form.avgCost);
    if (!form.ticker.trim()) return setFormErr("Please enter a stock symbol.");
    if (!form.shares || Number.isNaN(shares) || shares <= 0)
      return setFormErr("Please enter a valid number of shares.");
    if (!form.avgCost || Number.isNaN(avgCost) || avgCost <= 0)
      return setFormErr("Please enter a valid buy price.");
    // avg_cost is Numeric(12,2) on the backend — round to stored precision.
    const avg_cost = Math.round(avgCost * 100) / 100;
    const symbol = form.ticker.trim().toUpperCase();
    const onError = () => setFormErr("Could not save the holding. Please try again.");
    const onSuccess = () => setFormOpen(false);

    if (editingId != null) {
      updateHoldingApi.mutate({ holdingId: editingId, shares, avg_cost }, { onSuccess, onError });
    } else if (portfolioId) {
      addHoldingApi.mutate({ symbol, shares, avg_cost }, { onSuccess, onError });
    } else {
      // First holding ever: auto-create the default portfolio (like web).
      createPortfolio.mutate("Main", {
        onSuccess: (p) =>
          addHoldingApi.mutate(
            { portfolioId: p.id, symbol, shares, avg_cost },
            { onSuccess, onError },
          ),
        onError,
      });
    }
  }

  const savingTrade = createTxn.isPending || createPortfolio.isPending;

  function openTrade() {
    setTrade(emptyTrade);
    setTradeErr("");
    setTradeOpen(true);
  }
  function saveTrade() {
    setTradeErr("");
    const quantity = Number(trade.quantity);
    const price = Number(trade.price);
    const symbol = trade.symbol.trim().toUpperCase();
    if (!symbol) return setTradeErr("Please enter a stock symbol.");
    // Backend requires a whole-share quantity > 0.
    if (!trade.quantity || !Number.isInteger(quantity) || quantity <= 0)
      return setTradeErr("Please enter a whole number of shares.");
    if (!trade.price || Number.isNaN(price) || price < 0)
      return setTradeErr("Please enter a valid price.");
    const onError = () => setTradeErr("Could not record the trade. Please try again.");
    const onSuccess = () => setTradeOpen(false);
    const payload = { symbol, side: trade.side, quantity, price };

    if (portfolioId) {
      createTxn.mutate({ portfolio_id: portfolioId, ...payload }, { onSuccess, onError });
    } else {
      // First activity ever: auto-create the default portfolio (like holdings).
      createPortfolio.mutate("Main", {
        onSuccess: (p) => createTxn.mutate({ portfolio_id: p.id, ...payload }, { onSuccess, onError }),
        onError,
      });
    }
  }

  const renderTxn = ({ item }: { item: StockTransaction }) => {
    const buy = item.side === "buy";
    const sell = item.side === "sell";
    const tint = buy ? colors.bull : sell ? colors.bear : colors.textMuted;
    const dateLabel = item.executed_at
      ? new Date(item.executed_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })
      : "";
    return (
      <GlassCard radius={14} intensity={16} style={styles.txnCard}>
        <View style={styles.between}>
          <Text style={{ fontWeight: "700", fontSize: 14 }} numberOfLines={1}>{item.symbol}</Text>
          <View style={[styles.sideBadge, { backgroundColor: tint + "22" }]}>
            <Text style={{ color: tint, fontSize: 10.5, fontWeight: "700" }}>{item.side.toUpperCase()}</Text>
          </View>
        </View>
        <Text variant="mono" style={{ fontSize: 12.5, marginTop: 6 }}>
          {item.quantity ?? 0} @ {fmtPKR(item.price ?? 0)}
        </Text>
        <Text variant="muted" style={{ fontSize: 11, marginTop: 2 }}>{dateLabel}</Text>
      </GlassCard>
    );
  };

  const header = (
    <View style={{ gap: 16 }}>
      <Text variant="display" style={{ fontFamily: AVENIR }}>Portfolio</Text>

      <View style={styles.row}>
        <PStat label="Portfolio Value" value={fmtPKR(totals.value)} />
        <PStat label="Total Invested" value={fmtPKR(totals.invested)} />
      </View>
      <View style={styles.row}>
        <PStat label="Total Gain" value={fmtPKR(totals.gain)} delta={totals.gainPct} />
        <PStat
          label="Today's P/L"
          value={fmtPKR(totals.today)}
          delta={networth ? totals.todayPct : undefined}
        />
      </View>

      <GlassCard style={{ gap: 12, padding: 16 }}>
        <Text variant="title">Performance vs KSE-100</Text>
        <Segmented options={Object.keys(RANGES)} value={range} onChange={setRange} />
        {perfLoading ? (
          <View style={[styles.chartPlaceholder, { width: chartW }]}>
            <Text variant="muted">Loading portfolio history…</Text>
          </View>
        ) : series.length < 2 ? (
          <View style={[styles.chartPlaceholder, { width: chartW }]}>
            <Text variant="muted" style={{ textAlign: "center" }}>
              No portfolio history yet. Add holdings to build your performance chart.
            </Text>
          </View>
        ) : (
          <AreaChart data={series} benchmark={benchmark} width={chartW} />
        )}
        <View style={{ flexDirection: "row", gap: 16 }}>
          <Legend color={colors.primary} label="Portfolio" />
          <Legend color={colors.textMuted} label="KSE-100" />
        </View>
      </GlassCard>

      {isLoggedIn && (
        <AiReportSheet
          title="AI Portfolio Report"
          subtitle={portfolioReport.data?.content?.headline ?? "Tap to generate a verified analysis of your holdings"}
          variant="compact"
          report={portfolioReport.data?.content}
          isLoading={portfolioReport.isPending}
          error={portfolioReport.error}
          loadingLabel="Analysing your portfolio…"
          emptyLabel="Tap to generate a verified analysis of your holdings"
          onOpen={() => {
            if (!portfolioReport.data && !portfolioReport.isPending) portfolioReport.mutate();
          }}
        />
      )}

      <GlassCard style={{ gap: 10, padding: 16, borderColor: colors.gold + "55" }}>
        <Text style={{ color: colors.gold, fontWeight: "700" }}>Haqeeqi Daulat™ — Real Returns</Text>
        <ReturnRow label="Nominal return" value="+12.73%" color={colors.bull} />
        <ReturnRow label="PKR devaluation" value="-16.2%" color={colors.bear} />
        <ReturnRow label="Real USD return" value="-3.2%" color={colors.bear} />
        <View style={styles.between}>
          <Text variant="secondary">Devaluation Shield Score</Text>
          <Text variant="mono" style={{ color: colors.gold }}>38 / 100</Text>
        </View>
      </GlassCard>

      {allocation.length > 0 && (
        <GlassCard style={{ alignItems: "center", gap: 12, padding: 16 }}>
          <Text variant="title" style={{ alignSelf: "flex-start" }}>Allocation by Sector</Text>
          <DonutChart segments={allocation} size={190} strokeWidth={20} centerLabel={fmtPKR(totals.value)} centerSub="value" />
          <View style={{ gap: 6, alignSelf: "stretch" }}>
            {allocation.map((a) => (
              <View key={a.label} style={styles.between}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <View style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: a.color }} />
                  <Text variant="secondary">{a.label}</Text>
                </View>
                <Text variant="mono" style={{ fontSize: 13 }}>{a.pct.toFixed(1)}%</Text>
              </View>
            ))}
          </View>
        </GlassCard>
      )}

      <Text variant="title">Holdings</Text>
    </View>
  );

  const footer = (
    <View style={{ marginTop: 12 }}>
      {portfoliosError ? (
        <View style={{ gap: 10, marginBottom: 12 }}>
          <Text variant="muted" style={{ textAlign: "center" }}>
            Could not load your portfolio. Check your connection and try again.
          </Text>
          <Button title="Retry" variant="outline" onPress={() => refetchPortfolios()} />
        </View>
      ) : listLoading ? (
        <Text variant="muted" style={{ textAlign: "center", marginBottom: 12 }}>
          Loading portfolio…
        </Text>
      ) : holdings.length === 0 ? (
        <Text variant="muted" style={{ textAlign: "center", marginBottom: 12 }}>
          No holdings yet. Add your first position.
        </Text>
      ) : null}
      <Button title="Add Holding" onPress={openAdd} icon={<Plus color={colors.primaryForeground} size={16} />} />

      {/* ── Stock Transactions (buy / sell ledger) ── */}
      <View style={{ marginTop: 24, gap: 10 }}>
        <View style={styles.between}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <ArrowLeftRight color={colors.textSecondary} size={16} />
            <Text variant="title">Transactions</Text>
          </View>
          {isLoggedIn && (
            <Pressable
              onPress={openTrade}
              hitSlop={8}
              style={[styles.addTradeBtn, { borderColor: colors.border }]}
              accessibilityRole="button"
              accessibilityLabel="Add trade"
            >
              <Plus color={colors.primary} size={14} />
              <Text style={{ color: colors.primary, fontSize: 12.5, fontWeight: "600" }}>Add trade</Text>
            </Pressable>
          )}
        </View>
        {!isLoggedIn ? (
          <Text variant="muted" style={{ textAlign: "center", paddingVertical: 12 }}>
            Sign in to record and view your trades.
          </Text>
        ) : txnsLoading ? (
          <Text variant="muted" style={{ textAlign: "center", paddingVertical: 12 }}>
            Loading transactions…
          </Text>
        ) : txnsError ? (
          <Text variant="muted" style={{ textAlign: "center", paddingVertical: 12 }}>
            Could not load transactions.
          </Text>
        ) : !transactions || transactions.length === 0 ? (
          <Text variant="muted" style={{ textAlign: "center", paddingVertical: 12 }}>
            No trades yet. Record your first buy or sell.
          </Text>
        ) : (
          <FlatList
            horizontal
            data={transactions}
            keyExtractor={(txn) => String(txn.id)}
            renderItem={renderTxn}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: 10, paddingVertical: 2 }}
          />
        )}
      </View>

      <View style={{ height: 20 }} />
    </View>
  );

  return (
    <GlassScreen>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <FlatList
          data={holdings}
          keyExtractor={(h) => String(h.id)}
          ListHeaderComponent={header}
          ListFooterComponent={footer}
          contentContainerStyle={{ padding: 16, paddingBottom: 28, gap: 8 }}
          showsVerticalScrollIndicator={false}
        renderItem={({ item }) => (
          <View style={styles.holdingWrap}>
            <View style={styles.holding}>
              <View style={{ flex: 1.2 }}>
                <Text style={{ fontWeight: "700", fontSize: 15 }}>{item.symbol}</Text>
                <Text variant="muted" style={{ marginTop: 2 }} numberOfLines={1}>
                  {sectorMap.get(item.symbol) ?? "Other"}
                </Text>
              </View>
              <View style={{ flex: 1, alignItems: "flex-end" }}>
                <Text variant="mono" style={{ fontSize: 13 }}>{fmtPKR(item.market_value ?? 0)}</Text>
                <Text variant="muted">{item.shares ?? 0} sh</Text>
              </View>
              <View style={{ flex: 1, alignItems: "flex-end" }}>
                <Change pct={item.pnl_pct ?? 0} />
                <Text variant="muted">{fmtPKR(item.unrealized_pnl ?? 0)}</Text>
              </View>
              <View style={styles.actions}>
                <Pressable onPress={() => openEdit(item)} hitSlop={12} accessibilityRole="button" accessibilityLabel={`Edit ${item.symbol}`}>
                  <Pencil color={colors.textMuted} size={15} />
                </Pressable>
                <Pressable onPress={() => remove(item)} hitSlop={12} accessibilityRole="button" accessibilityLabel={`Delete ${item.symbol}`}>
                  <Trash2 color={colors.textMuted} size={15} />
                </Pressable>
              </View>
            </View>
            <Pressable
              style={styles.aiLink}
              onPress={() => router.push("/(tabs)/psx")}
              accessibilityRole="button"
              accessibilityLabel={`${item.symbol}: go to PSX Market for AI analysis`}
            >
              <Text style={styles.aiLinkText}>Go to PSX Market for AI analysis</Text>
              <ArrowRight color={colors.primary} size={13} />
            </Pressable>
          </View>
        )}
      />

      <GlassSheet open={formOpen} onClose={() => setFormOpen(false)} title={editingId == null ? "Add Holding" : "Edit Holding"}>
        <Field
          label="Stock symbol"
          value={form.ticker}
          onChangeText={(v) => setForm({ ...form, ticker: v })}
          placeholder="e.g. HBL"
          autoCapitalize="characters"
          editable={editingId == null}
        />
        <Field label="Shares" value={form.shares} onChangeText={(v) => setForm({ ...form, shares: v })} keyboardType="numeric" placeholder="0" />
        <Field label="Avg Cost (PKR)" value={form.avgCost} onChangeText={(v) => setForm({ ...form, avgCost: v })} keyboardType="numeric" placeholder="0" />
        {formErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{formErr}</Text> : null}
        <Button
          title={editingId == null ? "Add Holding" : "Save Changes"}
          onPress={saveHolding}
          loading={saving}
        />
      </GlassSheet>

      <GlassSheet open={tradeOpen} onClose={() => setTradeOpen(false)} title="Add Trade">
        <Segmented
          options={["Buy", "Sell"]}
          value={trade.side === "buy" ? "Buy" : "Sell"}
          onChange={(v) => setTrade({ ...trade, side: v === "Buy" ? "buy" : "sell" })}
        />
        <Field
          label="Stock symbol"
          value={trade.symbol}
          onChangeText={(v) => setTrade({ ...trade, symbol: v })}
          placeholder="e.g. HBL"
          autoCapitalize="characters"
        />
        <Field
          label="Quantity (shares)"
          value={trade.quantity}
          onChangeText={(v) => setTrade({ ...trade, quantity: v })}
          keyboardType="numeric"
          placeholder="0"
        />
        <Field
          label="Price (PKR)"
          value={trade.price}
          onChangeText={(v) => setTrade({ ...trade, price: v })}
          keyboardType="numeric"
          placeholder="0"
        />
        {tradeErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{tradeErr}</Text> : null}
        <Button title="Record Trade" onPress={saveTrade} loading={savingTrade} />
      </GlassSheet>
      </SafeAreaView>
    </GlassScreen>
  );
}

function PStat({ label, value, delta }: { label: string; value: string; delta?: number }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <GlassCard radius={16} intensity={20} style={styles.statCard}>
      <Text variant="muted" numberOfLines={1}>{label}</Text>
      <Text
        style={{ fontFamily: fonts.mono, fontSize: 17, marginTop: 6, color: colors.textPrimary }}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.7}
      >
        {value}
      </Text>
      {delta !== undefined && <Change pct={delta} />}
    </GlassCard>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <View style={{ width: 14, height: 3, backgroundColor: color, borderRadius: 2 }} />
      <Text variant="muted">{label}</Text>
    </View>
  );
}

function ReturnRow({ label, value, color }: { label: string; value: string; color: string }) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <View style={styles.between}>
      <Text variant="secondary">{label}</Text>
      <Text style={{ color, fontFamily: fonts.mono }}>{value}</Text>
    </View>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    safe: { flex: 1 },
    statCard: { flex: 1, padding: 14 },
    row: { flexDirection: "row", gap: 12 },
    between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
    chartPlaceholder: {
      height: 180,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 8,
      borderWidth: 1,
      borderStyle: "dashed",
      borderColor: c.border,
      paddingHorizontal: 16,
    },
    holdingWrap: { paddingVertical: 12, borderBottomColor: c.border, borderBottomWidth: 1 },
    holding: { flexDirection: "row", alignItems: "center" },
    aiLink: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 8, alignSelf: "flex-start" },
    aiLinkText: { fontFamily: AVENIR_MED, fontSize: 12, color: c.primary },
    actions: { flexDirection: "row", gap: 12, paddingLeft: 12 },
    txnCard: { width: 150, padding: 12 },
    sideBadge: { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
    addTradeBtn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      borderWidth: 1,
      borderRadius: 8,
      paddingHorizontal: 10,
      paddingVertical: 8,
      minHeight: 36,
    },
  });
