// Dashboard top ribbon: liquid-glass stock search with ticker/company typeahead,
// a notifications bell (unread badge → glass panel), and an account avatar
// (→ glass menu: upgrade / settings / sign out). All one cohesive glass system.
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";

import { GlassCard } from "@/components/glass/GlassCard";
import { GlassSheet } from "@/components/glass/GlassSheet";
import { SignalBadge, Text } from "@/components/ui";
import { fonts, radii, type ThemeColors } from "@/constants/theme";
import { useTheme } from "@/hooks/use-theme";
import { useAuth } from "@/hooks/use-auth";
import { useFinanceStore } from "@/hooks/use-finance-store";
import { Bell, ChevronRight, Crown, iconFor, LogOut, Search, Settings, X } from "@/lib/icons";
import { fmtNum, STOCK_LIST } from "@nafaiq/shared";

export function TopRibbon() {
  const { colors, mode } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const router = useRouter();
  const { profile, user, signOut } = useAuth();
  const { notifications } = useFinanceStore();
  const [q, setQ] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);
  const [acctOpen, setAcctOpen] = useState(false);

  const matches = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    return STOCK_LIST.filter((k) => k.ticker.toLowerCase().includes(s) || k.name.toLowerCase().includes(s)).slice(0, 6);
  }, [q]);

  const unread = notifications.filter((n) => !n.read).length;
  const initial = (profile?.display_name || user?.email || "U").trim().charAt(0).toUpperCase();

  function openStock(ticker: string) {
    setQ("");
    router.push(`/stock/${ticker}`);
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        {/* Search */}
        <GlassCard radius={radii.btn} intensity={20} sheen={0.1} style={styles.search}>
          <Search color={colors.textMuted} size={17} />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="Search stocks (e.g. HBL)…"
            placeholderTextColor={colors.textMuted}
            style={styles.searchInput}
            autoCapitalize="characters"
            autoCorrect={false}
            returnKeyType="search"
            accessibilityLabel="Search stocks"
          />
          {q.length > 0 && (
            <Pressable onPress={() => setQ("")} hitSlop={10} accessibilityLabel="Clear search">
              <X color={colors.textMuted} size={16} />
            </Pressable>
          )}
        </GlassCard>

        {/* Notifications */}
        <Pressable
          onPress={() => setNotifOpen(true)}
          style={styles.iconBtn}
          accessibilityRole="button"
          accessibilityLabel={`Notifications${unread ? `, ${unread} unread` : ""}`}
        >
          <GlassCard radius={radii.full} intensity={22} sheen={0.12} style={styles.iconInner}>
            <Bell color={colors.textSecondary} size={19} />
          </GlassCard>
          {unread > 0 && (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{unread > 9 ? "9+" : unread}</Text>
            </View>
          )}
        </Pressable>

        {/* Account */}
        <Pressable
          onPress={() => setAcctOpen(true)}
          style={styles.iconBtn}
          accessibilityRole="button"
          accessibilityLabel="Account menu"
        >
          <GlassCard radius={radii.full} intensity={22} sheen={0.14} style={styles.iconInner}>
            <Text style={styles.avatar}>{initial}</Text>
          </GlassCard>
        </Pressable>
      </View>

      {/* Typeahead dropdown */}
      {matches.length > 0 && (
        <GlassCard radius={16} intensity={40} sheen={0.14} style={styles.dropdown}>
          <View style={[StyleSheet.absoluteFill, { backgroundColor: mode === "light" ? "rgba(255,255,255,0.6)" : "rgba(7,12,26,0.55)" }]} pointerEvents="none" />
          {matches.map((m, i) => (
            <Pressable
              key={m.ticker}
              onPress={() => openStock(m.ticker)}
              style={[styles.suggest, i > 0 && styles.suggestBorder]}
              accessibilityRole="button"
              accessibilityLabel={`${m.ticker}, ${m.name}`}
            >
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "700", fontSize: 14 }}>{m.ticker}</Text>
                <Text variant="muted" numberOfLines={1}>{m.name}</Text>
              </View>
              <Text style={styles.suggestPrice}>{fmtNum(m.price)}</Text>
              <SignalBadge signal={m.signal} />
            </Pressable>
          ))}
        </GlassCard>
      )}

      {/* Notifications panel */}
      <GlassSheet open={notifOpen} onClose={() => setNotifOpen(false)} title="Notifications">
        {notifications.length === 0 ? (
          <Text variant="secondary" style={{ paddingVertical: 12 }}>You&apos;re all caught up.</Text>
        ) : (
          <ScrollView style={{ maxHeight: 360 }} showsVerticalScrollIndicator={false}>
            {notifications.map((n, i) => {
              const Icon = iconFor(n.emoji);
              return (
                <View key={i} style={[styles.notif, !n.read && { backgroundColor: colors.primary + "0f" }]}>
                  <View style={styles.notifIcon}>
                    <Icon color={colors.primary} size={16} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 13.5 }}>{n.msg}</Text>
                    <Text variant="muted" style={{ marginTop: 2 }}>{n.time}</Text>
                  </View>
                  {!n.read && <View style={styles.unreadDot} />}
                </View>
              );
            })}
          </ScrollView>
        )}
      </GlassSheet>

      {/* Account menu */}
      <GlassSheet open={acctOpen} onClose={() => setAcctOpen(false)} title={profile?.display_name || user?.email?.split("@")[0] || "Account"}>
        <Text variant="muted" style={{ marginTop: -4 }}>{profile?.plan ?? "Free"} plan · {user?.email ?? "—"}</Text>
        <MenuItem icon={Crown} label="Upgrade to Pro" tint={colors.gold} onPress={() => { setAcctOpen(false); router.push("/plans"); }} />
        <MenuItem icon={Settings} label="Settings" onPress={() => { setAcctOpen(false); router.push("/settings"); }} />
        <MenuItem
          icon={LogOut}
          label="Sign out"
          tint={colors.bear}
          onPress={() =>
            Alert.alert("Sign out", "Are you sure you want to sign out?", [
              { text: "Cancel", style: "cancel" },
              { text: "Sign out", style: "destructive", onPress: () => { setAcctOpen(false); signOut(); } },
            ])
          }
        />
      </GlassSheet>
    </View>
  );
}

function MenuItem({
  icon: Icon,
  label,
  tint,
  onPress,
}: {
  icon: typeof Crown;
  label: string;
  tint?: string;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.menuItem, pressed && { opacity: 0.7 }]} accessibilityRole="button" accessibilityLabel={label}>
      <View style={[styles.menuIcon, { backgroundColor: (tint ?? colors.primary) + "1f" }]}>
        <Icon color={tint ?? colors.textSecondary} size={17} />
      </View>
      <Text style={{ flex: 1, fontWeight: "600", color: tint ?? colors.textPrimary }}>{label}</Text>
      <ChevronRight color={colors.textMuted} size={18} />
    </Pressable>
  );
}

const makeStyles = (c: ThemeColors) =>
  StyleSheet.create({
    wrap: { zIndex: 20 },
    row: { flexDirection: "row", alignItems: "center", gap: 10 },
    search: { flex: 1, height: 44, flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12 },
    searchInput: { flex: 1, color: c.textPrimary, fontSize: 14, fontFamily: fonts.sans, height: 44 },
    iconBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    iconInner: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    avatar: { color: c.textPrimary, fontWeight: "800", fontSize: 15 },
    badge: { position: "absolute", top: 2, right: 2, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: c.bear, alignItems: "center", justifyContent: "center", paddingHorizontal: 3 },
    badgeText: { color: "#fff", fontSize: 9, fontWeight: "800" },

    dropdown: { position: "absolute", top: 52, left: 0, right: 98, padding: 4, zIndex: 30, elevation: 12 },
    suggest: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10, paddingHorizontal: 10 },
    suggestBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: c.border },
    suggestPrice: { fontFamily: fonts.mono, fontSize: 13, color: c.textSecondary },

    notif: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 11, paddingHorizontal: 10, borderRadius: 12 },
    notifIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: c.primary + "1a", alignItems: "center", justifyContent: "center" },
    unreadDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: c.primary },

    menuItem: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, marginTop: 2 },
    menuIcon: { width: 36, height: 36, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  });
