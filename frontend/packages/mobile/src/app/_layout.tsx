// Root layout: provider tree + theme + auth-gated navigator.
// Mirrors the web app's __root.tsx (QueryClient → Auth → Learn → Theme → gate).
import {
  DarkTheme as NavDark,
  DefaultTheme as NavLight,
  ThemeProvider as NavThemeProvider,
} from "@react-navigation/native";
import { QueryClientProvider } from "@tanstack/react-query";
import { type ErrorBoundaryProps, Stack, usePathname, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text as RNText, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";

import { WallpaperWarmup } from "@/components/glass/GlassScreen";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LearnProvider } from "@/hooks/use-learn";
import { usePlatformFlags } from "@/hooks/queries/use-platform-flags";
import { ThemeProvider as AppThemeProvider, useTheme } from "@/hooks/use-theme";
import { darkColors, fonts } from "@/constants/theme";
import { queryClient } from "@/lib/query-client";
import { reportClientError } from "@/lib/telemetry";

export const unstable_settings = { initialRouteName: "index" };

// Public (unauthenticated-allowed) top-level routes — matches web AuthGate.
const PUBLIC_ROUTES = ["", "index", "auth", "plans"];

function RootNavigator() {
  const { user, profile, loading } = useAuth();
  const { colors, mode } = useTheme();
  const segments = useSegments();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { maintenanceMode } = usePlatformFlags();

  const top = segments[0] ?? "";
  const inPublic = PUBLIC_ROUTES.includes(top);

  // Onboarding plan gate — mirrors web Dashboard's needsPlanSelection:
  // a signed-in user whose profile has no plan_selected_at must pick a plan
  // before entering the app. (profile !== null waits for the profile fetch so
  // we never redirect on a not-yet-loaded profile.)
  const needsPlanSelection = !!user && profile !== null && !profile.plan_selected_at;

  useEffect(() => {
    if (loading) return;
    if (!user && !inPublic) {
      router.replace("/auth");
    } else if (needsPlanSelection && top !== "plans") {
      router.replace("/plans");
    } else if (user && top === "auth") {
      router.replace("/(tabs)/app");
    }
  }, [user, loading, inPublic, top, needsPlanSelection, router]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <NavThemeProvider value={mode === "dark" ? NavDark : NavLight}>
      <StatusBar style={mode === "dark" ? "light" : "dark"} />
      <View style={{ flex: 1 }}>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.background },
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="auth" />
          <Stack.Screen name="plans" options={{ presentation: "modal" }} />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="settings" />
          <Stack.Screen name="help" />
          <Stack.Screen name="monetary" />
          <Stack.Screen name="watchlist" />
          <Stack.Screen name="ai-insights" />
          <Stack.Screen name="fund/[code]" />

          <Stack.Screen name="alerts" />
          <Stack.Screen name="assistant" />
          <Stack.Screen name="stock/[ticker]" />
        </Stack>
        {maintenanceMode && top !== "auth" ? (
          <View pointerEvents="none" style={[rootStyles.maintenance, { backgroundColor: colors.warning, top: insets.top }]} accessibilityRole="alert">
            <RNText style={rootStyles.maintenanceText}>Maintenance mode · Some live services may be unavailable</RNText>
          </View>
        ) : null}
      </View>
    </NavThemeProvider>
  );
}

/** Route-level crash screen with anonymous-safe telemetry and a local retry. */
export function ErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const pathname = usePathname();
  useEffect(() => {
    void reportClientError(error, pathname);
  }, [error, pathname]);

  return (
    <View style={rootStyles.errorRoot}>
      <View style={rootStyles.errorCard}>
        <RNText style={rootStyles.errorEyebrow}>NAFAIQ RECOVERY</RNText>
        <RNText style={rootStyles.errorTitle}>Something interrupted this screen.</RNText>
        <RNText style={rootStyles.errorBody}>The issue was reported automatically. Retry without leaving your current journey.</RNText>
        <Pressable onPress={() => void retry()} style={rootStyles.retry} accessibilityRole="button">
          <RNText style={rootStyles.retryText}>Try again</RNText>
        </Pressable>
      </View>
    </View>
  );
}

const rootStyles = StyleSheet.create({
  maintenance: { position: "absolute", top: 0, left: 0, right: 0, zIndex: 100, paddingTop: 4, paddingBottom: 7, paddingHorizontal: 16, alignItems: "center" },
  maintenanceText: { color: darkColors.background, fontSize: 11, fontWeight: "700" },
  errorRoot: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: darkColors.background },
  errorCard: { borderWidth: 1, borderColor: darkColors.borderHover, borderRadius: 20, padding: 24, backgroundColor: darkColors.surface, gap: 10 },
  errorEyebrow: { color: darkColors.primary, fontSize: 11, fontWeight: "800", letterSpacing: 1.6 },
  errorTitle: { color: darkColors.textPrimary, fontSize: 26, fontWeight: "800", fontFamily: fonts.heading },
  errorBody: { color: darkColors.textSecondary, fontSize: 14, lineHeight: 21 },
  retry: { marginTop: 8, minHeight: 48, borderRadius: 10, backgroundColor: darkColors.primary, alignItems: "center", justifyContent: "center" },
  retryText: { color: darkColors.primaryForeground, fontWeight: "800" },
});

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      {/* Decode the contour wallpapers into expo-image's cache during startup
          so no screen ever shows the background popping in. */}
      <WallpaperWarmup />
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <LearnProvider>
              <AppThemeProvider>
                <RootNavigator />
              </AppThemeProvider>
            </LearnProvider>
          </AuthProvider>
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
