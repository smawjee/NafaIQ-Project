// Settings (`/settings`). Mirrors web /settings: language toggle (EN/UR),
// appearance/theme toggle (dark/light), account info. Wires the theme + lang
// foundations so the user can actually switch them.
import { useState } from "react";
import { Alert, Platform, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Text } from "@/components/ui";
import { fonts, type ThemeMode } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { type Lang, useLang } from "@/hooks/use-lang";
import { useTheme } from "@/hooks/use-theme";
import { Check, Languages, LogOut, Monitor, Moon, Sun } from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

export default function SettingsScreen() {
  const { colors, mode, setMode } = useTheme();
  const { lang, setLang, t } = useLang();
  const { profile, user, signOut } = useAuth();
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  const [signingOut, setSigningOut] = useState(false);

  // Signing out clears the Supabase session; the root auth gate then redirects
  // to /auth automatically, so no manual navigation is needed here.
  const confirmSignOut = () => {
    Alert.alert(t("Sign out"), t("Are you sure you want to sign out?"), [
      { text: t("Cancel"), style: "cancel" },
      {
        text: t("Sign out"),
        style: "destructive",
        onPress: async () => {
          setSigningOut(true);
          try {
            await signOut();
          } finally {
            setSigningOut(false);
          }
        },
      },
    ]);
  };

  return (
    <GlassScreen>
      <SafeAreaView style={{ flex: 1 }} edges={["top", "left", "right"]}>
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          <View style={{ marginBottom: 2 }}>
            <Text variant="display" style={{ fontFamily: AVENIR }}>{t("Settings")}</Text>
            <Text variant="secondary" style={{ marginTop: 2 }}>{t("Personalise how NafaIQ looks and feels.")}</Text>
          </View>

          {/* Language */}
          <GlassCard style={styles.card}>
        <View style={styles.head}>
          <Languages color={colors.primary} size={16} />
          <Text variant="title" style={{ fontSize: 15 }}>{t("Language")}</Text>
        </View>
        <Text variant="secondary" style={{ fontSize: 13 }}>{t("Choose the language for the app interface.")}</Text>
        <View style={{ gap: 10 }}>
          {(["en", "ur"] as Lang[]).map((v) => (
            <OptionRow
              key={v}
              active={lang === v}
              onPress={() => setLang(v)}
              badge={<Text style={{ fontFamily: v === "ur" ? fonts.urdu : undefined, color: lang === v ? colors.primary : colors.textSecondary, fontWeight: "700" }}>{v === "ur" ? "اُ" : "A"}</Text>}
              title={v === "en" ? "English" : t("Urdu")}
              desc={v === "en" ? "Standard interface language" : t("Right-to-left Urdu interface")}
            />
          ))}
        </View>
      </GlassCard>

      {/* Appearance */}
      <GlassCard style={styles.card}>
        <View style={styles.head}>
          <Monitor color={colors.primary} size={16} />
          <Text variant="title" style={{ fontSize: 15 }}>{t("Appearance")}</Text>
        </View>
        <Text variant="secondary" style={{ fontSize: 13 }}>
          {t("Choose the theme for your dashboard. This applies to the app only — the public site stays dark.")}
        </Text>
        <View style={{ gap: 10 }}>
          {(["dark", "light"] as ThemeMode[]).map((v) => {
            const Icon = v === "dark" ? Moon : Sun;
            return (
              <OptionRow
                key={v}
                active={mode === v}
                onPress={() => setMode(v)}
                badge={<Icon color={mode === v ? colors.primary : colors.textSecondary} size={18} />}
                title={t(v === "dark" ? "Dark" : "Light")}
                desc={v === "dark" ? "Default OLED-friendly terminal look" : "Bright, high-contrast daytime view"}
              />
            );
          })}
        </View>
      </GlassCard>

      {/* Account */}
      <GlassCard style={styles.card}>
        <Text variant="title" style={{ fontSize: 15 }}>{t("Account")}</Text>
        <Row label={t("Name")} value={name} />
        <Row label={t("Email")} value={user?.email ?? "—"} />
        <Row label={t("Plan")} value={profile?.plan ?? "Free"} />
        <View style={{ marginTop: 6 }}>
          <Button
            title={t("Sign out")}
            onPress={confirmSignOut}
            loading={signingOut}
            variant="outline"
            icon={<LogOut color={colors.bear} size={16} />}
          />
        </View>
          </GlassCard>
        </ScrollView>
      </SafeAreaView>
    </GlassScreen>
  );
}

function OptionRow({
  active,
  onPress,
  badge,
  title,
  desc,
}: {
  active: boolean;
  onPress: () => void;
  badge: React.ReactNode;
  title: string;
  desc: string;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected: active }}
      style={[styles.option, { borderColor: active ? colors.primary : colors.border, backgroundColor: active ? colors.primary + "1a" : colors.surface }]}
    >
      <View style={[styles.badge, { backgroundColor: active ? colors.primary + "22" : colors.hover }]}>{badge}</View>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <Text style={{ fontWeight: "600", fontSize: 13 }}>{title}</Text>
          {active && <Check color={colors.primary} size={14} />}
        </View>
        <Text variant="muted" style={{ marginTop: 2 }}>{desc}</Text>
      </View>
    </Pressable>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.between}>
      <Text variant="muted">{label}</Text>
      <Text style={{ fontWeight: "600" }}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 40, gap: 16 },
  card: { padding: 16, gap: 12 },
  head: { flexDirection: "row", alignItems: "center", gap: 8 },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  option: { flexDirection: "row", alignItems: "flex-start", gap: 12, borderWidth: 1, borderRadius: 12, padding: 14 },
  badge: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
});
