import { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, TextInput, View } from "react-native";
import { useQueryClient } from "@tanstack/react-query";

import { GlassCard } from "@/components/glass/GlassCard";
import { Screen } from "@/components/Screen";
import { Button, Text } from "@/components/ui";
import { ChipRow } from "@/components/ui/controls";
import { fonts, type ThemeColors } from "@/constants/theme";
import { type MonetarySnapshot, useMonetarySnapshot } from "@/hooks/queries/use-macro";
import { useTheme } from "@/hooks/use-theme";
import { publicGet } from "@/lib/api";
import { ArrowRightLeft, Coins, RefreshCw, ShieldCheck } from "@/lib/icons";

function pkr(value: number, digits = 2) {
  return `PKR ${value.toLocaleString("en-PK", { maximumFractionDigits: digits })}`;
}

function validationLabel(status?: MonetarySnapshot["validation"]["status"]) {
  return status === "cross_checked" ? "Cross-checked" : status === "review" ? "Needs review" : "Single source";
}

export default function MonetaryScreen() {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const query = useMonetarySnapshot();
  const qc = useQueryClient();
  const [amount, setAmount] = useState("1");
  const [from, setFrom] = useState("USD");
  const [to, setTo] = useState("PKR");
  const [refreshing, setRefreshing] = useState(false);
  const data = query.data;
  const codes = useMemo(() => data?.currencies.map((item) => item.code) ?? ["USD", "PKR"], [data]);
  const converted = useMemo(() => {
    const n = Number(amount);
    const fromRate = data?.rates[from];
    const toRate = data?.rates[to];
    return Number.isFinite(n) && fromRate && toRate ? (n / fromRate) * toRate : null;
  }, [amount, data, from, to]);

  async function refreshLive() {
    setRefreshing(true);
    try {
      const fresh = await publicGet<MonetarySnapshot>("/api/macro/monetary?refresh=true");
      qc.setQueryData(["macro", "monetary"], fresh);
    } finally {
      setRefreshing(false);
    }
  }

  if (query.isPending) {
    return <Screen title="Monetary Desk" back><ActivityIndicator color={colors.primary} size="large" /></Screen>;
  }
  if (query.isError || !data) {
    return <Screen title="Monetary Desk" back><GlassCard style={styles.center}><Text variant="title">Live monetary data is unavailable.</Text><Text variant="secondary">The provider may be temporarily offline.</Text><Button title="Try again" onPress={() => query.refetch()} /></GlassCard></Screen>;
  }

  return (
    <Screen title="Monetary Desk" subtitle="Live reference FX and Pakistan bullion prices." back>
      <GlassCard style={styles.hero}>
        <View style={styles.between}>
          <View>
            <Text variant="muted">DOLLAR TO PKR</Text>
            <Text style={styles.heroValue}>{pkr(data.usd_pkr)}</Text>
            <Text variant="muted">for 1 US Dollar</Text>
          </View>
          <View style={[styles.liveBadge, { borderColor: (data.stale ? colors.warning : colors.bull) + "55" }]}>
            <Text style={{ color: data.stale ? colors.warning : colors.bull, fontSize: 11, fontWeight: "700" }}>{data.stale ? "CACHED" : "LIVE"}</Text>
          </View>
        </View>
        <View style={styles.sourceGrid}>
          <Source label="FX source" value={data.source.name} colors={colors} />
          <Source label="Metal source" value={data.metal_source?.name ?? "Spot fallback"} colors={colors} />
          <Source label="Quality" value={validationLabel(data.validation.status)} colors={colors} />
          <Source label="Updated" value={new Date(data.refreshed_at).toLocaleString()} colors={colors} />
        </View>
      </GlassCard>

      <GlassCard style={{ gap: 14 }}>
        <View style={styles.between}>
          <View style={{ flex: 1 }}><Text variant="title">Currency converter</Text><Text variant="secondary" style={{ fontSize: 13 }}>Converted through the live USD reference.</Text></View>
          <Pressable onPress={() => { setFrom(to); setTo(from); }} style={styles.swap} accessibilityRole="button" accessibilityLabel="Swap currencies"><ArrowRightLeft color={colors.primary} size={18} /></Pressable>
        </View>
        <TextInput value={amount} onChangeText={setAmount} keyboardType="decimal-pad" placeholder="1" placeholderTextColor={colors.textMuted} style={styles.input} accessibilityLabel="Amount to convert" />
        <Text variant="muted">FROM</Text>
        <ChipRow options={codes} value={from} onChange={setFrom} />
        <View style={styles.result}><Text style={styles.resultValue}>{converted == null ? "—" : converted.toLocaleString("en-PK", { maximumFractionDigits: to === "PKR" ? 2 : 4 })}</Text><Text variant="title">{to}</Text></View>
        <Text variant="muted">TO</Text>
        <ChipRow options={codes} value={to} onChange={setTo} />
        <Button title="Refresh live rates" variant="outline" loading={refreshing} onPress={refreshLive} icon={<RefreshCw color={colors.primary} size={16} />} />
      </GlassCard>

      <Text variant="title">Pakistan bullion</Text>
      {data.metals.map((metal) => (
        <GlassCard key={metal.code} style={{ gap: 10 }}>
          <View style={styles.between}>
            <View style={styles.metalTitle}><Coins color={metal.code === "XAU" ? colors.gold : colors.textSecondary} size={20} /><View><Text variant="title">{metal.name}</Text><Text variant="muted">{metal.basis}</Text></View></View>
            <Text variant="mono" style={{ fontSize: 17 }}>{pkr(metal.pkr_per_tola, 0)}</Text>
          </View>
          <View style={styles.metalGrid}>
            <Metric label="Per gram" value={pkr(metal.pkr_per_gram, 0)} />
            <Metric label="Per 10g" value={pkr(metal.pkr_per_10g, 0)} />
            <Metric label="Per tola" value={pkr(metal.pkr_per_tola, 0)} />
          </View>
          <Text variant="muted">{metal.source_name ?? "Live provider"}{metal.city ? ` · ${metal.city}` : ""}{metal.cadence ? ` · ${metal.cadence}` : ""}</Text>
        </GlassCard>
      ))}

      <GlassCard style={styles.disclaimer}>
        <ShieldCheck color={colors.primary} size={17} />
        <Text variant="muted" style={{ flex: 1, lineHeight: 18 }}>{data.disclaimer} {data.warnings.join(" ")}</Text>
      </GlassCard>
    </Screen>
  );
}

function Source({ label, value, colors }: { label: string; value: string; colors: ThemeColors }) {
  return <View style={{ width: "48%", borderWidth: 1, borderColor: colors.border, backgroundColor: colors.glassFill, borderRadius: 10, padding: 10 }}><Text variant="muted">{label.toUpperCase()}</Text><Text style={{ fontSize: 12, fontWeight: "700", marginTop: 4 }} numberOfLines={1}>{value}</Text></View>;
}
function Metric({ label, value }: { label: string; value: string }) { return <View style={{ flex: 1, gap: 3 }}><Text variant="muted">{label}</Text><Text variant="mono" style={{ fontSize: 11 }}>{value}</Text></View>; }

const makeStyles = (c: ThemeColors) => StyleSheet.create({
  center: { alignItems: "center", gap: 12, paddingVertical: 28 },
  hero: { gap: 16 },
  between: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  heroValue: { fontFamily: fonts.heading, fontSize: 30, fontWeight: "800", marginVertical: 4 },
  liveBadge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5, backgroundColor: c.glassFill },
  sourceGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  swap: { width: 42, height: 42, borderRadius: 12, borderWidth: 1, borderColor: c.border, backgroundColor: c.glassFill, alignItems: "center", justifyContent: "center" },
  input: { minHeight: 52, borderWidth: 1, borderColor: c.border, borderRadius: 10, backgroundColor: c.glassFill, color: c.textPrimary, paddingHorizontal: 14, fontFamily: fonts.mono, fontSize: 18 },
  result: { minHeight: 62, borderWidth: 1, borderColor: c.primary + "44", borderRadius: 12, backgroundColor: c.primary + "0e", paddingHorizontal: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  resultValue: { color: c.textPrimary, fontFamily: fonts.mono, fontSize: 22, flex: 1 },
  metalTitle: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1 },
  metalGrid: { flexDirection: "row", gap: 8, borderTopWidth: 1, borderTopColor: c.border, paddingTop: 10 },
  disclaimer: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
});
