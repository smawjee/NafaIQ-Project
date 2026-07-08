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

import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LearnProvider } from "@/hooks/use-learn";
import { ThemeProvider as AppThemeProvider, useTheme } from "@/hooks/use-theme";
import { queryClient } from "@/lib/query-client";

export const unstable_settings = { initialRouteName: "index" };

// Public (unauthenticated-allowed) top-level routes — matches web AuthGate.
const PUBLIC_ROUTES = ["", "index", "auth", "plans"];

function RootNavigator() {
  const { user, loading } = useAuth();
  const { colors, mode } = useTheme();
  const segments = useSegments();
  const router = useRouter();

  const top = segments[0] ?? "";
  const inPublic = PUBLIC_ROUTES.includes(top);

  useEffect(() => {
    if (loading) return;
    if (!user && !inPublic) {
      router.replace("/auth");
    } else if (user && top === "auth") {
      router.replace("/(tabs)/app");
    }
  }, [user, loading, inPublic, top, router]);

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

        <Stack.Screen name="alerts" options={{ headerShown: true, title: "Alerts" }} />
        <Stack.Screen name="stock/[ticker]" options={{ headerShown: true, title: "Stock" }} />
      </Stack>
    </NavThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
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
