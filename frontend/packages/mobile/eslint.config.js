// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    // supabase/functions are Deno (separate runtime) — not part of the app lint.
    ignores: ["dist/*", "supabase/**"],
  }
]);
