// Bottom-tab navigator (auth-gated group). Icons-only, liquid-glass bar with a
// frosted blur background and a glowing glass "pill" behind the active icon.
import { BlurView } from "expo-blur";
import { Tabs } from "expo-router";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { colors } from "@/constants/theme";
import { Briefcase, GraduationCap, LayoutDashboard, type LucideIcon, TrendingUp, Wallet } from "@/lib/icons";

export const unstable_settings = { initialRouteName: "app" };

function TabIcon({ Icon, focused }: { Icon: LucideIcon; focused: boolean }) {
  return (
    <View style={[styles.pill, focused && styles.pillActive]}>
      <Icon color={focused ? colors.primary : colors.textMuted} size={22} strokeWidth={focused ? 2.4 : 2} />
    </View>
  );
}

function GlassTabBar() {
  return (
    <View style={StyleSheet.absoluteFill}>
      <BlurView intensity={36} tint="dark" experimentalBlurMethod="dimezisBlurView" style={StyleSheet.absoluteFill} />
      <View style={[StyleSheet.absoluteFill, { backgroundColor: "rgba(18,19,22,0.72)" }]} />
      <View style={styles.hairline} />
    </View>
  );
}

export default function TabsLayout() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: colors.background },
        tabBarShowLabel: false,
        tabBarBackground: () => <GlassTabBar />,
        tabBarStyle: {
          backgroundColor: "transparent",
          borderTopWidth: 0,
          elevation: 0,
          height: 44 + insets.bottom,
          paddingTop: 5,
          paddingBottom: insets.bottom,
        },
      }}
    >
      <Tabs.Screen
        name="app"
        options={{ title: "Home", tabBarIcon: ({ focused }) => <TabIcon Icon={LayoutDashboard} focused={focused} /> }}
      />
      <Tabs.Screen
        name="psx"
        options={{ title: "Markets", tabBarIcon: ({ focused }) => <TabIcon Icon={TrendingUp} focused={focused} /> }}
      />
      <Tabs.Screen
        name="portfolio"
        options={{ title: "Portfolio", tabBarIcon: ({ focused }) => <TabIcon Icon={Briefcase} focused={focused} /> }}
      />
      <Tabs.Screen
        name="finance"
        options={{ title: "Finance", tabBarIcon: ({ focused }) => <TabIcon Icon={Wallet} focused={focused} /> }}
      />
      <Tabs.Screen
        name="learn"
        options={{ title: "Learn", tabBarIcon: ({ focused }) => <TabIcon Icon={GraduationCap} focused={focused} /> }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  pill: { width: 50, height: 30, borderRadius: 11, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "transparent" },
  pillActive: { backgroundColor: colors.primary + "1f", borderColor: colors.primary + "55" },
  hairline: { position: "absolute", top: 0, left: 0, right: 0, height: StyleSheet.hairlineWidth, backgroundColor: colors.borderHover },
});
