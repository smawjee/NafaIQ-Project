// Jest setup — global mocks for native modules the component tree touches so
// unit tests run without a device. @testing-library/react-native v13 registers
// its matchers automatically.

// Supabase client: never hit the network from a test. Individual tests can
// override getSession's resolved value.
jest.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: jest.fn().mockResolvedValue({ data: { session: null } }),
    },
  },
}));

// Reanimated ships a Jest mock; wire it so animated components render.
jest.mock("react-native-reanimated", () =>
  require("react-native-reanimated/mock"),
);

// AsyncStorage's native module isn't present under Jest — use its official mock.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
