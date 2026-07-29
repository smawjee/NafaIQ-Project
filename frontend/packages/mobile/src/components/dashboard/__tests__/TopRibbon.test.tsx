// The account menu is the assistant's ONLY entry point, and the plan row must
// upsell free users without nagging paid ones — both worth locking in.
/* eslint-disable import/first -- jest.mock must precede the mocked imports (jest hoists it) */
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import React from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({ useRouter: () => ({ push: mockPush }) }));

const mockAuth = {
  profile: { display_name: "Tayyib", plan: "Free" },
  user: { email: "t@example.com" },
  signOut: jest.fn(),
};
jest.mock("@/hooks/use-auth", () => ({ useAuth: () => mockAuth }));
jest.mock("@/hooks/queries/use-notifications", () => ({
  useNotifications: () => ({ data: [] }),
  useMarkNotificationRead: () => ({ mutate: jest.fn() }),
}));
jest.mock("@/hooks/queries/use-market", () => ({
  useStockUniverse: () => [],
  matchStocks: () => [],
}));

import { TopRibbon } from "@/components/dashboard/TopRibbon";
import { ThemeProvider } from "@/hooks/use-theme";

function renderRibbon() {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { x: 0, y: 0, width: 390, height: 844 },
        insets: { top: 0, left: 0, right: 0, bottom: 0 },
      }}
    >
      <ThemeProvider>
        <TopRibbon />
      </ThemeProvider>
    </SafeAreaProvider>,
  );
}

async function openMenu(utils: ReturnType<typeof renderRibbon>) {
  fireEvent.press(utils.getByLabelText("Account menu"));
  await waitFor(() => expect(utils.getByText("Settings")).toBeTruthy());
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAuth.profile = { display_name: "Tayyib", plan: "Free" };
});

describe("TopRibbon account menu", () => {
  it("offers the NafaIQ Assistant and routes to /assistant", async () => {
    const utils = renderRibbon();
    await openMenu(utils);

    fireEvent.press(utils.getByText("NafaIQ Assistant"));
    expect(mockPush).toHaveBeenCalledWith("/assistant");
  });

  it("shows Upgrade to Pro for free users", async () => {
    const utils = renderRibbon();
    await openMenu(utils);

    expect(utils.getByText("Upgrade to Pro")).toBeTruthy();
    expect(utils.queryByText("Manage Plan")).toBeNull();
  });

  it.each(["Pro", "Premium"])("shows Manage Plan for %s users, still routing to /plans", async (plan) => {
    mockAuth.profile = { display_name: "Tayyib", plan };
    const utils = renderRibbon();
    await openMenu(utils);

    expect(utils.queryByText("Upgrade to Pro")).toBeNull();
    fireEvent.press(utils.getByText("Manage Plan"));
    expect(mockPush).toHaveBeenCalledWith("/plans");
  });
});
