// Plans & pricing (`/plans`, public modal). Mirrors web /plans: billing toggle,
// 3 tier cards (Pro highlighted), feature comparison table. Liquid-glass, theme
// aware.
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Alert, Platform, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Text } from "@/components/ui";
import { fonts, type ThemeColors } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { useLang } from "@/hooks/use-lang";
import { usePlan, useUpgradePlan } from "@/hooks/queries/use-plan";
import { useTheme } from "@/hooks/use-theme";
import { Check, Minus, Star, X } from "@/lib/icons";
import type { Plan } from "@/lib/plan-features";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

type Billing = "monthly" | "yearly";

const TIERS = [
  { id: "free", name: "Free", tagline: "Get started with the essentials", monthly: 0, yearly: 0, cta: "Get Started", mail: false, highlight: false, features: ["Delayed PSX data", "1 portfolio", "Basic finance tracker", "Zakat calculator", "3 AI Advisor queries / month"] },
  { id: "pro", name: "Pro", tagline: "For serious investors", monthly: 1499, yearly: 1199, cta: "Upgrade to Pro", mail: false, highlight: true, features: ["Real-time PSX data", "Unlimited AI Advisor", "Full Haqeeqi Daulat breakdown", "Unlimited portfolios & watchlists", "Halal screening filters", "Priority alerts"] },
  { id: "premium", name: "Premium", tagline: "For families & power users", monthly: null as number | null, yearly: null as number | null, cta: "Contact Us", mail: true, highlight: false, features: ["Everything in Pro", "Multi-account / family tracking", "Advanced data export", "Priority support"] },
];

const COMPARISON = [
  { label: "Data delay", free: "15 min", pro: "Real-time", premium: "Real-time" },
  { label: "Portfolios", free: "1", pro: "Unlimited", premium: "Unlimited" },
  { label: "AI Advisor", free: "3 / mo", pro: "Unlimited", premium: "Unlimited" },
  { label: "Watchlists", free: "1", pro: "Unlimited", premium: "Unlimited" },
  { label: "Alerts", free: "Basic", pro: "Priority", premium: "Priority" },
  { label: "Halal screening", free: "—", pro: "✓", premium: "✓" },
  { label: "Support", free: "Community", pro: "Standard", premium: "Priority" },
];

function priceOf(t: (typeof TIERS)[number], b: Billing) {
  const v = b === "monthly" ? t.monthly : t.yearly;
  if (v === null) return "Custom";
  if (v === 0) return "Free";
  return `PKR ${v.toLocaleString()}`;
}

export default function PlansScreen() {
  const [billing, setBilling] = useState<Billing>("monthly");
  const { colors } = useTheme();
  const { t } = useLang();
  const router = useRouter();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const { user, profile, signOut } = useAuth();
  const { plan } = usePlan();
  const upgrade = useUpgradePlan();
  // Onboarding = logged in but hasn't confirmed a plan yet. New profiles default
  // to "Free", so during onboarding we must NOT lock the Free button as the
  // "current plan" — the user still needs to tap it to stamp plan_selected_at
  // and leave the plan gate. Only lock a tier once a plan has been confirmed.
  const hasConfirmedPlan = !!profile?.plan_selected_at;
  const onboarding = !!user && !hasConfirmedPlan;

  const selectTier = async (tierName: string) => {
    try {
      await upgrade.mutateAsync(tierName as Plan);
      router.replace("/(tabs)/app");
    } catch {
      Alert.alert(t("Failed to change plan"), t("Please try again."));
    }
  };

  return (
    <GlassScreen>
      <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
        <View style={styles.topbar}>
          <Text variant="title">{t("Plans & Pricing")}</Text>
          {onboarding ? (
            // The plan gate bounces users without a confirmed plan back here,
            // so during onboarding offer sign-out instead of a dead close button.
            <Pressable
              onPress={async () => {
                await signOut();
                router.replace("/auth");
              }}
              hitSlop={12}
              style={styles.signOutBtn}
              accessibilityRole="button"
              accessibilityLabel={t("Sign out")}
            >
              <Text variant="secondary" style={{ fontWeight: "600" }}>{t("Sign out")}</Text>
            </Pressable>
          ) : (
            <Pressable onPress={() => router.back()} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close">
              <X color={colors.textSecondary} size={22} />
            </Pressable>
          )}
        </View>

        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={{ alignItems: "center", gap: 8 }}>
            <Text style={styles.heading}>{t("Affordable Prices. Premium Features. Premium Feel.")}</Text>
            <Text variant="secondary" style={{ textAlign: "center" }}>
              {t("Start free. Upgrade when you're ready for real-time data and unlimited AI insights.")}
            </Text>
          </View>

          {/* billing toggle */}
          <View style={styles.toggle}>
            <Pressable
              onPress={() => setBilling("monthly")}
              style={[styles.toggleBtn, billing === "monthly" && { backgroundColor: colors.bull }]}
              accessibilityRole="button"
              accessibilityState={{ selected: billing === "monthly" }}
            >
              <Text style={{ fontWeight: "700", color: billing === "monthly" ? colors.bullForeground : colors.textSecondary }}>{t("Monthly")}</Text>
            </Pressable>
            <Pressable
              onPress={() => setBilling("yearly")}
              style={[styles.toggleBtn, billing === "yearly" && { backgroundColor: colors.bull }]}
              accessibilityRole="button"
              accessibilityState={{ selected: billing === "yearly" }}
            >
              <Text style={{ fontWeight: "700", color: billing === "yearly" ? colors.bullForeground : colors.textSecondary }}>{t("Yearly")}</Text>
              <View style={styles.saveBadge}>
                <Text style={{ color: colors.gold, fontSize: 10, fontWeight: "700" }}>{t("SAVE 20%")}</Text>
              </View>
            </Pressable>
          </View>

          {/* tier cards */}
          {TIERS.map((tier) => (
            <View key={tier.id} style={styles.tierWrap}>
              {tier.highlight && (
                <View style={styles.popular}>
                  <Star color={colors.bullForeground} size={12} fill={colors.bullForeground} />
                  <Text style={{ color: colors.bullForeground, fontSize: 11, fontWeight: "700" }}>{t("MOST POPULAR")}</Text>
                </View>
              )}
              <GlassCard style={[styles.tier, tier.highlight && { borderColor: colors.bull + "88" }]}>
              <Text variant="title">{t(tier.name)}</Text>
              <Text variant="secondary">{t(tier.tagline)}</Text>
              <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 6, marginTop: 12 }}>
                <Text style={{ fontFamily: fonts.mono, fontSize: 28, fontWeight: "700", color: colors.textPrimary }}>{t(priceOf(tier, billing))}</Text>
                {tier.monthly !== null && tier.monthly !== 0 && <Text variant="muted" style={{ marginBottom: 4 }}>{t("/ mo")}</Text>}
              </View>
              {billing === "yearly" && tier.yearly !== null && tier.yearly !== 0 && (
                <Text style={{ color: colors.gold, fontSize: 11 }}>{t("Billed annually — 20% off")}</Text>
              )}
              <View style={{ marginTop: 14 }}>
                {user ? (
                  (() => {
                    const isCurrent = hasConfirmedPlan && plan === tier.name;
                    const pendingThis = upgrade.isPending && upgrade.variables === tier.name;
                    return (
                      <Button
                        title={
                          pendingThis
                            ? t("Saving…")
                            : isCurrent
                              ? t("Current Plan")
                              : !hasConfirmedPlan && tier.id === "free"
                                ? t("Get Started")
                                : `${t("Choose")} ${tier.name}`
                        }
                        variant={tier.highlight ? "primary" : "outline"}
                        loading={pendingThis}
                        disabled={isCurrent || upgrade.isPending}
                        onPress={() => selectTier(tier.name)}
                      />
                    );
                  })()
                ) : (
                  <Button
                    title={t(tier.cta)}
                    variant={tier.highlight ? "primary" : "outline"}
                    onPress={() => router.replace("/auth")}
                  />
                )}
              </View>
              <View style={{ gap: 10, marginTop: 16 }}>
                {tier.features.map((f) => (
                  <View key={f} style={{ flexDirection: "row", gap: 10 }}>
                    <Check color={colors.bull} size={16} />
                    <Text variant="secondary" style={{ flex: 1 }}>{t(f)}</Text>
                  </View>
                ))}
              </View>
              </GlassCard>
            </View>
          ))}

          {/* comparison table */}
          <Text variant="title" style={{ textAlign: "center", marginTop: 8 }}>{t("Compare plans")}</Text>
          <GlassCard style={styles.table}>
            <View style={styles.tr}>
              <Text style={[styles.th, { flex: 1.4, textAlign: "left" }]}>{t("Feature")}</Text>
              <Text style={styles.th}>Free</Text>
              <Text style={[styles.th, { color: colors.bull }]}>Pro</Text>
              <Text style={styles.th}>Premium</Text>
            </View>
            {COMPARISON.map((row, i) => (
              <View key={row.label} style={[styles.tr, i % 2 === 1 && { backgroundColor: colors.hover }]}>
                <Text variant="secondary" style={[styles.cell, { flex: 1.4, textAlign: "left" }]}>{t(row.label)}</Text>
                {[row.free, row.pro, row.premium].map((c, ci) => (
                  <View key={ci} style={styles.cellWrap}>
                    {c === "✓" ? (
                      <Check color={colors.bull} size={16} />
                    ) : c === "—" ? (
                      <Minus color={colors.textMuted} size={16} />
                    ) : (
                      <Text variant="mono" style={{ fontSize: 12, textAlign: "center", color: colors.textPrimary }}>{c}</Text>
                    )}
                  </View>
                ))}
              </View>
            ))}
          </GlassCard>
          <View style={{ height: 24 }} />
        </ScrollView>
      </SafeAreaView>
    </GlassScreen>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    topbar: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 12 },
    signOutBtn: { minHeight: 44, justifyContent: "center", paddingHorizontal: 8 },
    content: { padding: 16, gap: 16 },
    heading: { fontFamily: AVENIR, fontSize: 22, fontWeight: "800", color: c.textPrimary, textAlign: "center", letterSpacing: -0.3, lineHeight: 28 },
    toggle: { flexDirection: "row", alignSelf: "center", borderWidth: 1, borderColor: c.input, borderRadius: 999, padding: 4, backgroundColor: c.glassFillStrong },
    toggleBtn: { flexDirection: "row", alignItems: "center", gap: 8, borderRadius: 999, paddingHorizontal: 18, paddingVertical: 9 },
    saveBadge: { backgroundColor: c.gold + "26", borderRadius: 999, paddingHorizontal: 6, paddingVertical: 2 },
    tierWrap: { marginTop: 20 },
    tier: { gap: 2, padding: 16 },
    popular: { position: "absolute", top: -12, alignSelf: "center", zIndex: 2, elevation: 4, flexDirection: "row", alignItems: "center", gap: 4, backgroundColor: c.bull, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 4 },
    table: { padding: 0, overflow: "hidden" },
    tr: { flexDirection: "row", alignItems: "center", borderBottomWidth: 1, borderBottomColor: c.border },
    th: { flex: 1, textAlign: "center", fontWeight: "700", color: c.textPrimary, paddingVertical: 12, fontSize: 12 },
    cell: { paddingVertical: 12, paddingHorizontal: 4 },
    cellWrap: { flex: 1, alignItems: "center", paddingVertical: 12 },
  });
