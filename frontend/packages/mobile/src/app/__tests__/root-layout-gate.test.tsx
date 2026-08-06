/**
 * Root navigator auth + plan gate (src/app/_layout.tsx).
 *
 * This is the highest-risk untested logic in the app: it decides who may enter
 * the tabs, who is bounced to /auth, and who must pick a plan first. A
 * regression here either locks every user out or lets an unauthenticated one in.
 *
 * RootNavigator is not exported, so the gate is exercised through the default
 * export with the provider tree's leaves mocked.
 */
import { render } from "@testing-library/react-native";
import React from "react";

const mockReplace = jest.fn();
const mockUseAuth = jest.fn();
const mockUseSegments = jest.fn();

jest.mock("expo-router", () => {
  const { View } = require("react-native");
  const Stack = ({ children }: { children?: React.ReactNode }) => <View>{children}</View>;
  Stack.displayName = "Stack";
  const Screen = ({ name }: { name: string }) => <View testID={`screen-${name}`} />;
  Screen.displayName = "Stack.Screen";
  Stack.Screen = Screen;
  return {
    Stack,
    useRouter: () => ({ replace: mockReplace, push: jest.fn(), back: jest.fn() }),
    useSegments: () => mockUseSegments(),
  };
});

jest.mock("@/hooks/use-auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => mockUseAuth(),
}));

jest.mock("@/hooks/use-learn", () => ({
  LearnProvider: ({ children }: { children: React.ReactNode }) => children,
}));

jest.mock("@/hooks/queries/use-platform-flags", () => ({
  usePlatformFlags: () => ({ registrationEnabled: true, maintenanceMode: false, isLoading: false }),
}));

jest.mock("@/components/glass/GlassScreen", () => ({
  WallpaperWarmup: () => null,
}));

jest.mock("expo-status-bar", () => ({ StatusBar: () => null }));

// GestureHandlerRootView calls into the native module on mount, which does not
// exist under jest-expo.
jest.mock("react-native-gesture-handler", () => {
  const { View } = require("react-native");
  return { GestureHandlerRootView: View };
});

// _layout.tsx mounts SafeAreaProvider with no initialMetrics. On a device it
// measures and then renders; under the test renderer there is nothing to
// measure, so it renders null forever and the navigator below it never mounts.
jest.mock("react-native-safe-area-context", () => {
  const { View } = require("react-native");
  const insets = { top: 47, right: 0, bottom: 34, left: 0 };
  return {
    SafeAreaProvider: ({ children }: { children: React.ReactNode }) => <View>{children}</View>,
    SafeAreaView: View,
    useSafeAreaInsets: () => insets,
    initialWindowMetrics: { frame: { x: 0, y: 0, width: 390, height: 844 }, insets },
  };
});

import RootLayout from "@/app/_layout";

const USER = { id: "u1", email: "t@example.com" };
const PROFILE_WITH_PLAN = { plan: "Free", plan_selected_at: "2026-07-01T00:00:00Z" };
const PROFILE_NO_PLAN = { plan: null, plan_selected_at: null };

function renderAt(segments: string[], auth: Record<string, unknown>) {
  mockUseSegments.mockReturnValue(segments);
  mockUseAuth.mockReturnValue({ user: null, profile: null, loading: false, ...auth });
  return render(<RootLayout />);
}

beforeEach(() => {
  mockReplace.mockClear();
  mockUseAuth.mockReset();
  mockUseSegments.mockReset();
});

describe("auth gate", () => {
  it("does not redirect while the session is still loading", () => {
    // Redirecting during bootstrap would bounce a signed-in user to /auth on
    // every cold start, before Supabase has restored the session.
    renderAt(["(tabs)"], { user: null, loading: true });

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows a spinner while loading rather than an empty screen", () => {
    const { UNSAFE_root } = renderAt(["(tabs)"], { user: null, loading: true });

    expect(UNSAFE_root.findAllByType(require("react-native").ActivityIndicator).length).toBe(1);
  });

  it.each([["(tabs)"], ["settings"], ["alerts"], ["assistant"], ["stock"]])(
    "sends an anonymous visitor on /%s to /auth",
    (segment) => {
      renderAt([segment], { user: null, loading: false });

      expect(mockReplace).toHaveBeenCalledWith("/auth");
    },
  );

  it.each([[""], ["index"], ["auth"], ["plans"]])(
    "leaves an anonymous visitor alone on the public route /%s",
    (segment) => {
      renderAt([segment], { user: null, loading: false });

      expect(mockReplace).not.toHaveBeenCalled();
    },
  );

  it("treats a missing first segment as the public root", () => {
    renderAt([], { user: null, loading: false });

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("moves a signed-in user off /auth into the tabs", () => {
    renderAt(["auth"], { user: USER, profile: PROFILE_WITH_PLAN, loading: false });

    expect(mockReplace).toHaveBeenCalledWith("/(tabs)/app");
  });

  it("leaves a signed-in user with a plan where they are", () => {
    renderAt(["(tabs)"], { user: USER, profile: PROFILE_WITH_PLAN, loading: false });

    expect(mockReplace).not.toHaveBeenCalled();
  });
});

describe("plan-selection gate", () => {
  it("forces a signed-in user with no plan_selected_at to /plans", () => {
    renderAt(["(tabs)"], { user: USER, profile: PROFILE_NO_PLAN, loading: false });

    expect(mockReplace).toHaveBeenCalledWith("/plans");
  });

  it("does NOT redirect while the profile is still null", () => {
    // profile === null means "not fetched yet", not "no plan". Without this
    // guard every signed-in user is thrown at /plans on each cold start.
    renderAt(["(tabs)"], { user: USER, profile: null, loading: false });

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("does not loop once the user is already on /plans", () => {
    renderAt(["plans"], { user: USER, profile: PROFILE_NO_PLAN, loading: false });

    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("takes priority over the signed-in-on-/auth redirect", () => {
    // Both branches match a planless user sitting on /auth; the plan gate is
    // checked first, so onboarding is never skipped.
    renderAt(["auth"], { user: USER, profile: PROFILE_NO_PLAN, loading: false });

    expect(mockReplace).toHaveBeenCalledWith("/plans");
    expect(mockReplace).not.toHaveBeenCalledWith("/(tabs)/app");
  });

  it("stops redirecting once a plan has been selected", () => {
    renderAt(["(tabs)"], { user: USER, profile: PROFILE_WITH_PLAN, loading: false });

    expect(mockReplace).not.toHaveBeenCalledWith("/plans");
  });
});

describe("navigator registration", () => {
  it("registers every top-level route the app links to", () => {
    const { getByTestId } = renderAt(["(tabs)"], {
      user: USER,
      profile: PROFILE_WITH_PLAN,
      loading: false,
    });

    for (const name of [
      "index",
      "auth",
      "plans",
      "(tabs)",
      "settings",
      "help",
      "monetary",
      "watchlist",
      "ai-insights",
      "fund/[code]",
      "alerts",
      "assistant",
      "stock/[ticker]",
    ]) {
      expect(getByTestId(`screen-${name}`)).toBeTruthy();
    }
  });
});
