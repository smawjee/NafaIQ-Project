/**
 * AI report client — typed fetchers for the backend /api/ai/report/* surfaces.
 * Ported from the web app's src/lib/ai/reports-client.ts.
 *
 * Reports return one complete, schema-validated JSON envelope (unlike the tutor
 * SSE stream). This attaches the Supabase JWT like the user tier in lib/api.ts,
 * but adds a typed error taxonomy so callers can tell quota (429) and
 * temporarily-unavailable (503) apart — the plain helpers collapse the status
 * into a message string the UI can't branch on.
 */
import type { ReportResponse } from "@nafaiq/shared";

import { getCurrentLang } from "@/hooks/use-lang";
import { apiUrl } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export type ReportErrorCode = "auth" | "quota" | "unavailable" | "network";

/** Typed report failure so the UI can show the right message per status. */
export class ReportError extends Error {
  code: ReportErrorCode;
  status?: number;
  constructor(code: ReportErrorCode, message: string, status?: number) {
    super(message);
    this.name = "ReportError";
    this.code = code;
    this.status = status;
  }
}

async function sessionToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

function withLang(path: string, lang?: string): string {
  const l = lang ?? getCurrentLang();
  return path + (path.includes("?") ? "&" : "?") + `lang=${l}`;
}

/** Map an HTTP status to the matching ReportError code. */
function reportErrorForStatus(status: number, path: string): ReportError {
  if (status === 401) return new ReportError("auth", "Session expired", 401);
  if (status === 429) return new ReportError("quota", "Quota exceeded", 429);
  if (status === 503) return new ReportError("unavailable", "Temporarily unavailable", 503);
  return new ReportError("unavailable", `${path}: ${status}`, status);
}

async function requestReport(path: string, method: "GET" | "POST"): Promise<ReportResponse> {
  const token = await sessionToken();
  if (!token) throw new ReportError("auth", "Not authenticated");

  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      ...(method === "POST" ? { body: "{}" } : {}),
    });
  } catch {
    throw new ReportError("network", "Network error");
  }

  if (!res.ok) throw reportErrorForStatus(res.status, path);
  return (await res.json()) as ReportResponse;
}

export function generatePortfolioReport(days = 180, lang?: string): Promise<ReportResponse> {
  return requestReport(withLang(`/api/ai/report/portfolio?days=${days}`, lang), "POST");
}

export function generateFinanceReport(lang?: string): Promise<ReportResponse> {
  return requestReport(withLang(`/api/ai/report/finance`, lang), "POST");
}

/**
 * Daily-cached dashboard nudge. `refresh` bypasses the cached row and
 * regenerates — NOT free (spends a report-quota unit, answers 429 when out), so
 * only ever send it for a deliberate user action, never a retry/refetch/mount.
 */
export function getDashboardRecommendation(lang?: string, refresh = false): Promise<ReportResponse> {
  const path = refresh
    ? "/api/ai/report/dashboard-recommendation?refresh=true"
    : "/api/ai/report/dashboard-recommendation";
  return requestReport(withLang(path, lang), "GET");
}

/**
 * Shared daily market brief (cached per trading date across all users).
 * `refresh` forces a new generation and is FREE — no per-user quota hit.
 */
export function getMarketBrief(lang?: string, refresh = false): Promise<ReportResponse> {
  const path = refresh
    ? "/api/ai/report/market-brief?refresh=true"
    : "/api/ai/report/market-brief";
  return requestReport(withLang(path, lang), "GET");
}

/** Per-symbol stock analysis. Backend POSTs to stock/{symbol}. */
export function generateStockReport(symbol: string, lang?: string): Promise<ReportResponse> {
  const upper = symbol.trim().toUpperCase();
  return requestReport(withLang(`/api/ai/report/stock/${encodeURIComponent(upper)}`, lang), "POST");
}

/** The (English) key describing a report failure — pass through t() at the call site. */
export function reportErrorKey(e: unknown): string {
  if (e instanceof ReportError) {
    if (e.code === "auth") return "Please sign in to generate your report.";
    if (e.code === "quota")
      return "You've reached your AI report limit for this period. Upgrade your plan to generate more.";
    if (e.code === "unavailable")
      return "This report is temporarily unavailable. Please try again shortly.";
  }
  return "Couldn't generate your report. Please try again.";
}
