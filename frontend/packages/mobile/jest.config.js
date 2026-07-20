/** Jest config for the Expo app. jest-expo provides the RN/Expo module mocks. */
module.exports = {
  preset: "jest-expo",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  // pnpm layout: real dependency files live under node_modules/.pnpm/<pkg>@<ver>/…,
  // so the usual `node_modules/(?!react-native…)` never matches and RN/Expo stay
  // untransformed. Gate on the .pnpm segment and allow the RN/Expo toolchain +
  // lucide (all ship untranspiled ESM) through the transformer. @nafaiq/shared is
  // a workspace symlink outside node_modules, so it is already transformed.
  transformIgnorePatterns: [
    "node_modules/.pnpm/(?!((jest-)?react-native|@react-native|@react-navigation|expo|@expo|@unimodules|unimodules|sentry-expo|native-base|lucide-react-native))",
  ],
};
