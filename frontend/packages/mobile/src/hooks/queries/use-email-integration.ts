// Bank-email import (Gmail OAuth). Mirrors web hooks/use-email-integration.ts —
// same endpoints and query keys. Scraping runs server-side, so connecting from
// either platform serves both.
//
// NOTE: Google rejects LAN-IP redirect URIs, so the OAuth round-trip only works
// when EXPO_PUBLIC_API_URL points at the deployed backend (https), not a
// laptop's http://192.168.x.x.
import { makeRedirectUri } from "expo-auth-session";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";

import { userDelete, userGet, userPost } from "@/lib/api";

export interface EmailIntegrationStatus {
  connected: boolean;
  google_email?: string;
  scope?: string | null;
  enabled?: boolean;
  last_polled_at?: string | null;
  /** Set when the Google grant expired or was revoked — prompt a reconnect. */
  last_error?: string | null;
}

export interface EmailSyncResult {
  scanned: number;
  candidates: number;
  imported: number;
  duplicates: number;
  skipped: number;
}

export function useEmailIntegration(enabled: boolean = true) {
  return useQuery<EmailIntegrationStatus>({
    queryKey: ["email_integration"],
    queryFn: () => userGet<EmailIntegrationStatus>("/api/integrations/email"),
    enabled,
    staleTime: 30_000,
  });
}

/**
 * Open Google consent in an auth session. We hand the backend the exact deep
 * link this client is listening on — an `exp://…/--/settings` URL in Expo Go or
 * `nafaiqmobile://settings` in a dev-client/standalone build — so the backend
 * bounces the browser back to a URL that actually reopens the app (same
 * mechanism as Google sign-in). The backend validates the scheme and carries it
 * inside the signed OAuth state.
 */
export function useConnectGmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const redirectUrl = makeRedirectUri({ scheme: "nafaiqmobile", path: "settings" });
      const { auth_url } = await userGet<{ auth_url: string }>(
        `/api/integrations/gmail/connect?platform=mobile&redirect=${encodeURIComponent(redirectUrl)}`,
      );
      const res = await WebBrowser.openAuthSessionAsync(auth_url, redirectUrl);
      if (res.type !== "success") return { status: res.type };
      const status = res.url.includes("gmail=connected")
        ? "connected"
        : res.url.includes("gmail=cancelled")
          ? "cancelled"
          : "error";
      return { status };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["email_integration"] });
    },
  });
}

export function useDisconnectEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => userDelete<{ disconnected: boolean }>("/api/integrations/email"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["email_integration"] });
    },
  });
}

export function useSyncEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => userPost<EmailSyncResult>("/api/integrations/email/sync", {}),
    onSuccess: () => {
      // A sync can create transactions — refresh finance and the status row.
      qc.invalidateQueries({ queryKey: ["email_integration"] });
      qc.invalidateQueries({ queryKey: ["finance"] });
    },
  });
}
