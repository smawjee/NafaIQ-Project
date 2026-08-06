import { useQuery } from "@tanstack/react-query";

import { publicGet } from "@/lib/api";

export interface PlatformFlags {
  registration_enabled: boolean | null;
  maintenance_mode: boolean | null;
}

const FALLBACK: PlatformFlags = {
  registration_enabled: true,
  maintenance_mode: false,
};

/** Consumer-visible platform switches. Fail open if the flag service is down. */
export function usePlatformFlags() {
  const query = useQuery<PlatformFlags>({
    queryKey: ["platform-flags"],
    queryFn: () => publicGet<PlatformFlags>("/api/platform/flags"),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
  });
  const flags = query.data ?? FALLBACK;
  return {
    registrationEnabled: flags.registration_enabled !== false,
    maintenanceMode: flags.maintenance_mode === true,
    isLoading: query.isLoading,
  };
}
