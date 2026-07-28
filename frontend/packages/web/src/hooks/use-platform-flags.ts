import { useQuery } from "@tanstack/react-query";
import { apiUrl } from "@/lib/api";

/**
 * Client-visible platform flags (`GET /api/platform/flags`).
 *
 * This is the consumer half of the admin console's Feature Flags screen for the
 * two flags that only the client can act on:
 *
 *  - `maintenance_mode`    — the API already returns 503 for everything, so the
 *                            app reads this to explain *why* rather than
 *                            surfacing raw request failures.
 *  - `registration_enabled` — sign-up goes straight from the browser to
 *                            Supabase Auth and never transits our backend, so
 *                            there is no request for the API to reject. This is
 *                            a UI gate, NOT access control; to hard-close
 *                            registration, disable sign-ups in Supabase Auth.
 *
 * Deliberately unauthenticated and fetched with a bare `fetch`: the endpoint is
 * in the backend's PUBLIC_PATHS and has to be readable before a session exists.
 * It returns only an allow-listed subset — no internal flags are exposed.
 */
export interface PlatformFlags {
  registration_enabled: boolean | null;
  maintenance_mode: boolean | null;
}

const FALLBACK: PlatformFlags = {
  // Fail open, matching the backend's own behaviour: if we can't read the
  // flags, never lock users out of registration or show a false maintenance
  // screen on top of an unrelated network blip.
  registration_enabled: true,
  maintenance_mode: false,
};

export function usePlatformFlags() {
  const query = useQuery<PlatformFlags>({
    queryKey: ["platform-flags"],
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
    refetchOnWindowFocus: true,
    queryFn: async () => {
      const res = await fetch(apiUrl("/api/platform/flags"));
      if (!res.ok) throw new Error(`platform flags: ${res.status}`);
      return (await res.json()) as PlatformFlags;
    },
  });

  const flags = query.data ?? FALLBACK;
  return {
    // `null` means the flag row is missing or retired — treat as the default.
    registrationEnabled: flags.registration_enabled !== false,
    maintenanceMode: flags.maintenance_mode === true,
    isLoading: query.isLoading,
  };
}
