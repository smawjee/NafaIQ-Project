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
import {
  useConnectGmail,
  useDisconnectEmail,
  useEmailIntegration,
  useSyncEmail,
} from "@/hooks/queries/use-email-integration";
import { useTheme } from "@/hooks/use-theme";
import { Check, Inbox, Languages, LogOut, Monitor, Moon, Sun } from "@/lib/icons";

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

      {/* Bank email import */}
      <BankEmailCard />

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

/**
 * Connect Gmail so bank transaction alerts import automatically.
 * Read-only OAuth — no password is ever stored, and the user can revoke access
 * from their Google account at any time.
 */
function BankEmailCard() {
  const { colors } = useTheme();
  const { t } = useLang();
  const { user } = useAuth();
  const status = useEmailIntegration(!!user);
  const connect = useConnectGmail();
  const disconnect = useDisconnectEmail();
  const sync = useSyncEmail();

  const connected = status.data?.connected;
  // Google "Testing" mode refresh tokens expire after 7 days — surface that as
  // an actionable reconnect rather than a silent stall.
  const needsReconnect = !!status.data?.last_error;

  const onConnect = async () => {
    try {
      const r = await connect.mutateAsync();
      if (r.status === "connected") {
        Alert.alert(t("Gmail connected"), t("We'll import bank transactions from this account."));
      } else if (r.status === "error") {
        Alert.alert(t("Could not connect"), t("Please try again."));
      }
    } catch (e) {
      Alert.alert(
        t("Could not connect"),
        e instanceof Error ? e.message : t("Please try again."),
      );
    }
  };

  const onSync = async () => {
    try {
      const r = await sync.mutateAsync();
      Alert.alert(
        t("Sync complete"),
        r.imported > 0
          ? `${t("Imported")} ${r.imported} ${t("transaction(s)")}.`
          : t("No new transactions found."),
      );
    } catch (e) {
      Alert.alert(t("Sync failed"), e instanceof Error ? e.message : t("Please try again."));
    }
  };

  const onDisconnect = () => {
    Alert.alert(t("Disconnect Gmail"), t("Stop importing and revoke access?"), [
      { text: t("Cancel"), style: "cancel" },
      {
        text: t("Disconnect"),
        style: "destructive",
        onPress: async () => {
          try {
            await disconnect.mutateAsync();
          } catch {
            Alert.alert(t("Could not disconnect"), t("Please try again."));
          }
        },
      },
    ]);
  };

  if (!user) return null;

  return (
    <GlassCard style={styles.card}>
      <View style={styles.head}>
        <Inbox color={colors.primary} size={16} />
        <Text variant="title" style={{ fontSize: 15 }}>{t("Bank email import")}</Text>
      </View>
      <Text variant="secondary" style={{ fontSize: 13 }}>
        {t("Connect the Gmail account your bank sends alerts to and NafaIQ will add those transactions automatically. Read-only — we only look at bank emails.")}
      </Text>

      {connected ? (
        <View style={{ gap: 10 }}>
          <View style={[styles.option, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontWeight: "600", fontSize: 13 }}>{status.data?.google_email}</Text>
              <Text variant="muted" style={{ marginTop: 2 }}>
                {status.data?.last_polled_at
                  ? `${t("Last checked")}: ${new Date(status.data.last_polled_at).toLocaleString()}`
                  : t("Not checked yet")}
              </Text>
              {needsReconnect ? (
                <Text style={{ marginTop: 4, fontSize: 11, color: colors.bear }}>
                  {status.data?.last_error}
                </Text>
              ) : null}
            </View>
          </View>
          {needsReconnect ? (
            <Button title={t("Reconnect Gmail")} onPress={onConnect} loading={connect.isPending} />
          ) : (
            <Button title={t("Sync now")} onPress={onSync} loading={sync.isPending} variant="outline" />
          )}
          <Button
            title={t("Disconnect")}
            onPress={onDisconnect}
            loading={disconnect.isPending}
            variant="outline"
          />
        </View>
      ) : (
        <View style={{ gap: 10 }}>
          <Button title={t("Connect Gmail")} onPress={onConnect} loading={connect.isPending} />
          <Text variant="muted">
            {t("You'll see a Google warning that the app isn't verified — that's expected while NafaIQ is in testing. Choose Advanced, then continue.")}
          </Text>
        </View>
      )}
    </GlassCard>
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
