// Settings (`/settings`). Mirrors web /settings: language toggle (EN/UR),
// appearance/theme toggle (dark/light), account info. Wires the theme + lang
// foundations so the user can actually switch them.
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GlassCard } from "@/components/glass/GlassCard";
import { GlassScreen } from "@/components/glass/GlassScreen";
import { Button, Text } from "@/components/ui";
import { ChipRow } from "@/components/ui/controls";
import { fonts, radii, type ThemeMode } from "@/constants/theme";
import { useAuth } from "@/hooks/use-auth";
import { type Lang, useLang } from "@/hooks/use-lang";
import {
  useConnectGmail,
  useDisconnectEmail,
  useEmailIntegration,
  useSyncEmail,
} from "@/hooks/queries/use-email-integration";
import {
  type FinanceSettings,
  useFinanceSettings,
  useUpdateFinanceSettings,
} from "@/hooks/queries/use-finance-settings";
import {
  type NotificationPrefs,
  useNotificationPrefs,
  useUpdateNotificationPrefs,
} from "@/hooks/queries/use-notification-prefs";
import { useTheme } from "@/hooks/use-theme";
import { supabase } from "@/lib/supabase";
import {
  Bell,
  Check,
  Inbox,
  Languages,
  LogOut,
  Mail,
  MessageSquare,
  Monitor,
  Moon,
  Pencil,
  Smartphone,
  Sun,
  Wallet,
  X,
} from "@/lib/icons";

const AVENIR = Platform.select({ ios: "Avenir-Heavy", default: fonts.sans });

const CURRENCIES = ["PKR", "USD", "AED", "SAR", "EUR", "GBP"];

export default function SettingsScreen() {
  const { colors, mode, setMode } = useTheme();
  const { lang, setLang, t } = useLang();
  const { profile, user, signOut, refreshProfile } = useAuth();
  const name = profile?.display_name || user?.email?.split("@")[0] || "User";
  const [signingOut, setSigningOut] = useState(false);

  // Inline display_name edit — writes straight to the Supabase `profiles` row
  // (RLS lets a user update their own row; `plan` is trigger-protected). No
  // backend route needed; refreshProfile() re-pulls the auth profile after.
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [savingName, setSavingName] = useState(false);
  const startEditName = () => {
    setNameDraft(profile?.display_name ?? "");
    setEditingName(true);
  };
  const saveName = async () => {
    if (!user) return;
    const next = nameDraft.trim();
    if (!next) {
      Alert.alert(t("Name required"), t("Please enter a display name."));
      return;
    }
    setSavingName(true);
    try {
      const { error } = await supabase
        .from("profiles")
        .update({ display_name: next })
        .eq("id", user.id);
      if (error) throw error;
      await refreshProfile();
      setEditingName(false);
    } catch {
      Alert.alert(t("Could not save"), t("Please try again."));
    } finally {
      setSavingName(false);
    }
  };

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

      {/* Notification preferences */}
      <NotificationPrefsCard />

      {/* Finance settings */}
      <FinanceSettingsCard />

      {/* Bank email import */}
      <BankEmailCard />

      {/* Account */}
      <GlassCard style={styles.card}>
        <Text variant="title" style={{ fontSize: 15 }}>{t("Account")}</Text>
        {editingName ? (
          <View style={{ gap: 8 }}>
            <Text variant="muted">{t("Name")}</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <TextInput
                value={nameDraft}
                onChangeText={setNameDraft}
                autoFocus
                placeholder={t("Display name")}
                placeholderTextColor={colors.textMuted}
                style={[styles.input, { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.surface }]}
                accessibilityLabel={t("Display name")}
              />
              <Pressable
                onPress={saveName}
                disabled={savingName}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={t("Save name")}
                style={[styles.iconBtn, { backgroundColor: colors.primary + "22" }]}
              >
                {savingName ? <ActivityIndicator size="small" color={colors.primary} /> : <Check color={colors.primary} size={18} />}
              </Pressable>
              <Pressable
                onPress={() => setEditingName(false)}
                disabled={savingName}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={t("Cancel")}
                style={[styles.iconBtn, { backgroundColor: colors.hover }]}
              >
                <X color={colors.textSecondary} size={18} />
              </Pressable>
            </View>
          </View>
        ) : (
          <View style={styles.between}>
            <Text variant="muted">{t("Name")}</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Text style={{ fontWeight: "600" }}>{name}</Text>
              <Pressable
                onPress={startEditName}
                hitSlop={10}
                accessibilityRole="button"
                accessibilityLabel={t("Edit name")}
              >
                <Pencil color={colors.textSecondary} size={15} />
              </Pressable>
            </View>
          </View>
        )}
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

const PREF_ROWS: {
  key: keyof NotificationPrefs;
  icon: typeof Bell;
  title: string;
  desc: string;
  fallback: boolean;
}[] = [
  { key: "in_app_alerts", icon: MessageSquare, title: "In-app", desc: "Show notifications inside the app", fallback: true },
  { key: "email_alerts", icon: Mail, title: "Email alerts", desc: "Price, bill, budget & goal alerts you set up", fallback: true },
  { key: "email_activity", icon: Mail, title: "Email activity & receipts", desc: "Emails when you add a transaction, trade, pay a bill, etc.", fallback: false },
  { key: "push_alerts", icon: Smartphone, title: "Push", desc: "Push notifications (requires device permission)", fallback: false },
];

/** Per-channel notification toggles — GET/PATCH /api/notifications/preferences. */
function NotificationPrefsCard() {
  const { colors } = useTheme();
  const { t } = useLang();
  const { user } = useAuth();
  const prefs = useNotificationPrefs(!!user);
  const update = useUpdateNotificationPrefs();
  if (!user) return null;

  const toggle = (key: keyof NotificationPrefs, fallback: boolean) => {
    const current = prefs.data?.[key] ?? fallback;
    update.mutate({ [key]: !current });
  };

  return (
    <GlassCard style={styles.card}>
      <View style={styles.head}>
        <Bell color={colors.primary} size={16} />
        <Text variant="title" style={{ fontSize: 15 }}>{t("Notifications")}</Text>
      </View>
      <Text variant="secondary" style={{ fontSize: 13 }}>
        {t("Choose how you want to be notified when alerts trigger.")}
      </Text>
      {prefs.isLoading ? (
        <ActivityIndicator color={colors.primary} />
      ) : (
        <View style={{ gap: 4 }}>
          {PREF_ROWS.map(({ key, icon: Icon, title, desc, fallback }) => {
            const on = prefs.data?.[key] ?? fallback;
            return (
              <View key={key} style={styles.prefRow}>
                <View style={[styles.badge, { backgroundColor: colors.hover }]}>
                  <Icon color={on ? colors.primary : colors.textSecondary} size={17} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: "600", fontSize: 13 }}>{t(title)}</Text>
                  <Text variant="muted" style={{ marginTop: 2 }}>{t(desc)}</Text>
                </View>
                <Switch
                  value={on}
                  onValueChange={() => toggle(key, fallback)}
                  disabled={update.isPending}
                  trackColor={{ true: colors.primary, false: colors.border }}
                  thumbColor="#fff"
                  accessibilityLabel={t(title)}
                />
              </View>
            );
          })}
        </View>
      )}
    </GlassCard>
  );
}

/** Currency + monthly income — GET/PATCH /api/finance/settings. */
function FinanceSettingsCard() {
  const { colors } = useTheme();
  const { t } = useLang();
  const { user } = useAuth();
  const settings = useFinanceSettings(!!user);
  const update = useUpdateFinanceSettings();
  const [currency, setCurrency] = useState("PKR");
  const [income, setIncome] = useState("");

  // Seed the local form once the settings load / change.
  useEffect(() => {
    if (settings.data) {
      setCurrency(settings.data.currency || "PKR");
      setIncome(settings.data.monthly_income ? String(settings.data.monthly_income) : "");
    }
  }, [settings.data]);

  if (!user) return null;

  const dirty =
    !!settings.data &&
    (currency !== (settings.data.currency || "PKR") ||
      income !== (settings.data.monthly_income ? String(settings.data.monthly_income) : ""));

  const onSave = () => {
    const body: Partial<FinanceSettings> = { currency };
    const parsed = Number(income);
    if (income.trim() && !Number.isNaN(parsed) && parsed >= 0) body.monthly_income = parsed;
    update.mutate(body, {
      onError: () => Alert.alert(t("Could not save"), t("Please try again.")),
    });
  };

  return (
    <GlassCard style={styles.card}>
      <View style={styles.head}>
        <Wallet color={colors.primary} size={16} />
        <Text variant="title" style={{ fontSize: 15 }}>{t("Finance")}</Text>
      </View>
      <Text variant="secondary" style={{ fontSize: 13 }}>
        {t("Your reporting currency and monthly income, used across the finance tools.")}
      </Text>
      {settings.isLoading ? (
        <ActivityIndicator color={colors.primary} />
      ) : (
        <View style={{ gap: 12 }}>
          <View style={{ gap: 6 }}>
            <Text variant="muted">{t("Currency")}</Text>
            <ChipRow options={CURRENCIES} value={currency} onChange={setCurrency} />
          </View>
          <View style={{ gap: 6 }}>
            <Text variant="muted">{t("Monthly income")}</Text>
            <TextInput
              value={income}
              onChangeText={setIncome}
              keyboardType="numeric"
              placeholder="0"
              placeholderTextColor={colors.textMuted}
              style={[styles.input, { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.surface }]}
              accessibilityLabel={t("Monthly income")}
            />
          </View>
          <Button
            title={t("Save")}
            onPress={onSave}
            loading={update.isPending}
            disabled={!dirty || update.isPending}
          />
        </View>
      )}
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 40, gap: 16 },
  card: { padding: 16, gap: 12 },
  head: { flexDirection: "row", alignItems: "center", gap: 8 },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  option: { flexDirection: "row", alignItems: "flex-start", gap: 12, borderWidth: 1, borderRadius: 12, padding: 14 },
  badge: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  prefRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8 },
  input: { flex: 1, borderWidth: 1, borderRadius: radii.btn, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14 },
  iconBtn: { width: 40, height: 40, borderRadius: radii.btn, alignItems: "center", justifyContent: "center" },
});
