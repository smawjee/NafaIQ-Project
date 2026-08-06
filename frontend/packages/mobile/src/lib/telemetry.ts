import Constants from "expo-constants";

import { publicPost } from "@/lib/api";

/** Best-effort crash capture. Telemetry must never create a second crash. */
export async function reportClientError(error: Error, route?: string): Promise<void> {
  try {
    await publicPost<{ status: string }>("/api/telemetry/errors", {
      message: error.message || "Unknown mobile error",
      stack: error.stack?.slice(0, 20_000),
      route,
      app_version: Constants.expoConfig?.version ?? "dev",
    });
  } catch {
    // Deliberately ignored: the app remains usable when telemetry is offline.
  }
}
