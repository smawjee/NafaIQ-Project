import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userDelete, userGet, userPost } from "@/lib/psx/client";

export interface EmailIntegrationStatus {
  connected: boolean;
  google_email?: string;
  scope?: string | null;
  enabled?: boolean;
  last_polled_at?: string | null;
  /** Set when the Google grant expired or was revoked — prompt a reconnect. */
  last_error?: string | null;
  /**
   * Emails that could not be read. Surfaced so an incomplete picture is VISIBLE
   * rather than silently incomplete — otherwise the user has no way to know a
   * receipt never made it in.
   */
  unparsed_count?: number;
  broker_confirmations?: {
    pending: number;
    imported: number;
    unsupported: number;
    failed: number;
  };
}

export interface EmailSyncResult {
  scanned: number;
  candidates: number;
  imported: number;
  duplicates: number;
  skipped: number;
  /** Legs of one order collapsed into a transaction that already existed. */
  merged: number;
  /** Declined/failed payments: recorded, deliberately not imported. */
  failed_txn: number;
  /** Emails still owed a retry. */
  parse_errors: number;
  broker_pending: number;
  broker_imported: number;
  broker_unsupported: number;
  broker_failed: number;
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
 * Fetch the Google consent URL, then hand the browser to Google. The backend
 * owns the whole OAuth exchange and redirects back to /settings?gmail=...
 */
export function useConnectGmail() {
  return useMutation({
    mutationFn: async () => {
      const { auth_url } = await userGet<{ auth_url: string }>(
        "/api/integrations/gmail/connect?platform=web",
      );
      window.location.href = auth_url;
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
      qc.invalidateQueries({ queryKey: ["broker_imports"] });
      qc.invalidateQueries({ queryKey: ["broker_accounts"] });
      qc.invalidateQueries({ queryKey: ["finance"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}
