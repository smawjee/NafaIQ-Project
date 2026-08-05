// Root layout: provider tree + theme + auth-gated navigator.
// Mirrors the web app's __root.tsx (QueryClient → Auth → Learn → Theme → gate).
import {
  DarkTheme as NavDark,
  DefaultTheme as NavLight,
  ThemeProvider as NavThemeProvider,
} from "@react-navigation/native";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { WallpaperWarmup } from "@/components/glass/GlassScreen";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LearnProvider } from "@/hooks/use-learn";
import { ThemeProvider as AppThemeProvider, useTheme } from "@/hooks/use-theme";
import { queryClient } from "@/lib/query-client";

export const unstable_settings = { initialRouteName: "index" };

// Public (unauthenticated-allowed) top-level routes — matches web AuthGate.
const PUBLIC_ROUTES = ["", "index", "auth", "plans"];

function RootNavigator() {
  const { user, profile, loading, recoveryInProgress } = useAuth();
  const { colors, mode } = useTheme();
  const segments = useSegments();
  const router = useRouter();

  const top = segments[0] ?? "";
  const inPublic = PUBLIC_ROUTES.includes(top);

  // Onboarding plan gate — mirrors web Dashboard's needsPlanSelection:
  // a signed-in user whose profile has no plan_selected_at must pick a plan
  // before entering the app. (profile !== null waits for the profile fetch so
  // we never redirect on a not-yet-loaded profile.)
  const needsPlanSelection = !!user && profile !== null && !profile.plan_selected_at;

  useEffect(() => {
    if (loading) return;
    // A password reset holds every redirect below: verifying the emailed code
    // signs the user in BEFORE they have set a new password, and bouncing them
    // to the tabs (or the plan gate) on that half-finished session would drop
    // them out of the flow at step 2.
    if (recoveryInProgress) return;
    if (!user && !inPublic) {
      router.replace("/auth");
    } else if (needsPlanSelection && top !== "plans") {
      router.replace("/plans");
    } else if (user && top === "auth") {
      router.replace("/(tabs)/app");
    }
  }, [user, loading, inPublic, top, needsPlanSelection, recoveryInProgress, router]);

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

        <Stack.Screen name="alerts" />
        <Stack.Screen name="assistant" />
        <Stack.Screen name="stock/[ticker]" />
      </Stack>
    </NavThemeProvider>
  );
}

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
