// Portfolio (`/portfolio`): summary stats, performance vs KSE-100, Haqeeqi
// Daulat™, sector allocation donut, holdings with add/edit/delete (local CRUD,
// matching web), + form modal.
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
import { Button, Change, Text } from "@/components/ui";
import { ChipRow, Segmented } from "@/components/ui/controls";
import { fonts, type ThemeColors } from "@/constants/theme";
import { holdingsActions, useHoldings } from "@/hooks/use-holdings-store";
import { useTheme } from "@/hooks/use-theme";
import { fmtPKR, generateOHLCV, type Holding, INDICES, type Signal } from "@nafaiq/shared";
import { ArrowRight, Pencil, Plus, Trash2 } from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });
const AVENIR_MED = Platform.select({ ios: "Avenir-Medium", default: fonts.sans });
const RANGES: Record<string, number> = { "1M": 30, "3M": 90, "6M": 180, "1Y": 260 };
const SIGNALS: Signal[] = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"];
const emptyForm = { ticker: "", sector: "", shares: "", avgCost: "", current: "", signal: "HOLD" as Signal };

export default function PortfolioScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { width } = useWindowDimensions();
  const chartW = width - 64;
  const [range, setRange] = useState("6M");

  const holdings = useHoldings();
  const [formOpen, setFormOpen] = useState(false);
  const [editIdx, setEditIdx] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [formErr, setFormErr] = useState("");

  const computed = useMemo(() => {
    const rows = holdings.map((h) => {
      const mkt = h.shares * h.current;
      const cost = h.shares * h.avgCost;
      const gain = mkt - cost;
      return { ...h, mkt, cost, gain, gainPct: cost > 0 ? (gain / cost) * 100 : 0 };
    });
    const value = rows.reduce((s, r) => s + r.mkt, 0);
    const invested = rows.reduce((s, r) => s + r.cost, 0);
    const gain = value - invested;
    return { rows, value, invested, gain, gainPct: invested > 0 ? (gain / invested) * 100 : 0 };
  }, [holdings]);

  const series = useMemo(
    () => generateOHLCV(7, computed.invested || 1, computed.value || 1, RANGES[range]).map((c) => c.close),
    [computed, range],
  );
  const benchmark = useMemo(
    () => generateOHLCV(1, INDICES[0].start, INDICES[0].end, RANGES[range]).map((c) => c.close),
    [range],
  );

  const allocation = useMemo<DonutSegment[]>(() => {
    const bySector = new Map<string, number>();
    computed.rows.forEach((r) => bySector.set(r.sector, (bySector.get(r.sector) ?? 0) + r.mkt));
    return [...bySector.entries()].map(([label, value], i) => ({
      label,
      value,
      color: colors.chart[i % colors.chart.length],
    }));
  }, [computed, colors.chart]);

  function openAdd() {
    setEditIdx(null);
    setForm(emptyForm);
    setFormErr("");
    setFormOpen(true);
  }
  function openEdit(idx: number) {
    const h = holdings[idx];
    setEditIdx(idx);
    setForm({ ticker: h.ticker, sector: h.sector, shares: String(h.shares), avgCost: String(h.avgCost), current: String(h.current), signal: h.signal });
    setFormErr("");
    setFormOpen(true);
  }
  function remove(idx: number) {
    holdingsActions.removeHolding(idx);
  }
  function saveHolding() {
    setFormErr("");
    const shares = Number(form.shares);
    const avgCost = Number(form.avgCost);
    const current = Number(form.current);
    if (!form.ticker.trim()) return setFormErr("Please enter a stock symbol.");
    if (!form.sector.trim()) return setFormErr("Please enter a sector.");
    if (!form.shares || Number.isNaN(shares) || shares <= 0) return setFormErr("Please enter a valid number of shares.");
    if (!form.avgCost || Number.isNaN(avgCost) || avgCost <= 0) return setFormErr("Please enter a valid average cost.");
    const cur = !form.current || Number.isNaN(current) || current <= 0 ? avgCost : current;
    const entry: Holding = { ticker: form.ticker.trim().toUpperCase(), sector: form.sector.trim(), shares, avgCost, current: cur, signal: form.signal };
    if (editIdx == null) holdingsActions.addHolding(entry);
    else holdingsActions.updateHolding(editIdx, entry);
    setFormOpen(false);
  }

  const header = (
    <View style={{ gap: 16 }}>
      <Text variant="display" style={{ fontFamily: AVENIR }}>Portfolio</Text>

      <View style={styles.row}>
        <PStat label="Portfolio Value" value={fmtPKR(computed.value)} />
        <PStat label="Total Invested" value={fmtPKR(computed.invested)} />
      </View>
      <View style={styles.row}>
        <PStat label="Total Gain" value={fmtPKR(computed.gain)} delta={computed.gainPct} />
        <PStat label="Today's P/L" value={fmtPKR(17480)} delta={2.08} />
      </View>

      <GlassCard style={{ gap: 12, padding: 16 }}>
        <Text variant="title">Performance vs KSE-100</Text>
        <Segmented options={Object.keys(RANGES)} value={range} onChange={setRange} />
        <AreaChart data={series} benchmark={benchmark} width={chartW} />
        <View style={{ flexDirection: "row", gap: 16 }}>
          <Legend color={colors.primary} label="Portfolio" />
          <Legend color={colors.textMuted} label="KSE-100" />
        </View>
      </GlassCard>

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
          <DonutChart segments={allocation} size={190} strokeWidth={20} centerLabel={fmtPKR(computed.value)} centerSub="value" />
          <View style={{ gap: 6, alignSelf: "stretch" }}>
            {allocation.map((a) => (
              <View key={a.label} style={styles.between}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                  <View style={{ width: 10, height: 10, borderRadius: 2, backgroundColor: a.color }} />
                  <Text variant="secondary">{a.label}</Text>
                </View>
                <Text variant="mono" style={{ fontSize: 13 }}>
                  {computed.value > 0 ? ((a.value / computed.value) * 100).toFixed(1) : "0.0"}%
                </Text>
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
      {holdings.length === 0 && (
        <Text variant="muted" style={{ textAlign: "center", marginBottom: 12 }}>
          No holdings yet. Add your first position.
        </Text>
      )}
      <Button title="Add Holding" onPress={openAdd} icon={<Plus color={colors.primaryForeground} size={16} />} />
      <View style={{ height: 20 }} />
    </View>
  );

  return (
    <GlassScreen>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        <FlatList
          data={computed.rows}
          keyExtractor={(h, i) => h.ticker + i}
          ListHeaderComponent={header}
          ListFooterComponent={footer}
          contentContainerStyle={{ padding: 16, paddingBottom: 28, gap: 8 }}
          showsVerticalScrollIndicator={false}
        renderItem={({ item, index }) => (
          <View style={styles.holdingWrap}>
            <View style={styles.holding}>
              <View style={{ flex: 1.2 }}>
                <Text style={{ fontWeight: "700", fontSize: 15 }}>{item.ticker}</Text>
                <Text variant="muted" style={{ marginTop: 2 }} numberOfLines={1}>{item.sector}</Text>
              </View>
              <View style={{ flex: 1, alignItems: "flex-end" }}>
                <Text variant="mono" style={{ fontSize: 13 }}>{fmtPKR(item.mkt)}</Text>
                <Text variant="muted">{item.shares} sh</Text>
              </View>
              <View style={{ flex: 1, alignItems: "flex-end" }}>
                <Change pct={item.gainPct} />
                <Text variant="muted">{fmtPKR(item.gain)}</Text>
              </View>
              <View style={styles.actions}>
                <Pressable onPress={() => openEdit(index)} hitSlop={6} accessibilityRole="button" accessibilityLabel={`Edit ${item.ticker}`}>
                  <Pencil color={colors.textMuted} size={15} />
                </Pressable>
                <Pressable onPress={() => remove(index)} hitSlop={6} accessibilityRole="button" accessibilityLabel={`Delete ${item.ticker}`}>
                  <Trash2 color={colors.textMuted} size={15} />
                </Pressable>
              </View>
            </View>
            <Pressable
              style={styles.aiLink}
              onPress={() => router.push("/(tabs)/psx")}
              accessibilityRole="button"
              accessibilityLabel={`${item.ticker}: go to PSX Market for AI analysis`}
            >
              <Text style={styles.aiLinkText}>Go to PSX Market for AI analysis</Text>
              <ArrowRight color={colors.primary} size={13} />
            </Pressable>
          </View>
        )}
      />

      <GlassSheet open={formOpen} onClose={() => setFormOpen(false)} title={editIdx == null ? "Add Holding" : "Edit Holding"}>
        <Field label="Stock symbol" value={form.ticker} onChangeText={(v) => setForm({ ...form, ticker: v })} placeholder="e.g. HBL" autoCapitalize="characters" />
        <Field label="Sector" value={form.sector} onChangeText={(v) => setForm({ ...form, sector: v })} placeholder="e.g. Banking" />
        <Field label="Shares" value={form.shares} onChangeText={(v) => setForm({ ...form, shares: v })} keyboardType="numeric" placeholder="0" />
        <Field label="Avg Cost (PKR)" value={form.avgCost} onChangeText={(v) => setForm({ ...form, avgCost: v })} keyboardType="numeric" placeholder="0" />
        <Field label="Current price (optional)" value={form.current} onChangeText={(v) => setForm({ ...form, current: v })} keyboardType="numeric" placeholder="0" />
        <Text variant="secondary">Signal</Text>
        <ChipRow options={SIGNALS} value={form.signal} onChange={(v) => setForm({ ...form, signal: v as Signal })} />
        {formErr ? <Text style={{ color: colors.bear, fontSize: 12 }}>{formErr}</Text> : null}
        <Button title={editIdx == null ? "Add Holding" : "Save Changes"} onPress={saveHolding} />
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
    holdingWrap: { paddingVertical: 12, borderBottomColor: c.border, borderBottomWidth: 1 },
    holding: { flexDirection: "row", alignItems: "center" },
    aiLink: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 8, alignSelf: "flex-start" },
    aiLinkText: { fontFamily: AVENIR_MED, fontSize: 12, color: c.primary },
    actions: { flexDirection: "row", gap: 12, paddingLeft: 12 },
  });
