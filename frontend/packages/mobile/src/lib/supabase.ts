// RN-adapted Supabase client. Ported from the web app's
// ../nafa-iq-zenith/src/integrations/supabase/client.ts, swapping localStorage
// for AsyncStorage and disabling URL session detection (no browser).
import "react-native-url-polyfill/auto";

import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient } from "@supabase/supabase-js";
import { AppState } from "react-native";

import type { Database } from "./database.types";

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  const missing = [
    ...(!SUPABASE_URL ? ["EXPO_PUBLIC_SUPABASE_URL"] : []),
    ...(!SUPABASE_ANON_KEY ? ["EXPO_PUBLIC_SUPABASE_ANON_KEY"] : []),
  ].join(", ");
  // Surface early & clearly, mirroring the web client's behavior.
  throw new Error(`[Supabase] Missing environment variable(s): ${missing}. See .env.example.`);
}

export const supabase = createClient<Database>(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// Supabase RN guidance: only auto-refresh the session while the app is in the
// foreground. Register once at module load.
AppState.addEventListener("change", (state) => {
  if (state === "active") supabase.auth.startAutoRefresh();
  else supabase.auth.stopAutoRefresh();
});
