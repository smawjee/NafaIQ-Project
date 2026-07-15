/**
 * AI report client — typed fetchers for the backend /api/ai/report/* surfaces.
 *
 * Unlike the tutor (SSE stream), reports return one complete, schema-validated
 * JSON envelope. This client mirrors `lib/psx/client.ts` (Supabase JWT attached
 * for user-scoped reports) but adds a typed error taxonomy so callers can tell
 * quota (429) and temporarily-unavailable (503) apart — the plain psx helpers
 * collapse the status into a message string, which the UI can't branch on.
 */
import { API_BASE_URL } from "@/lib/api";
import { getCurrentLang } from "@/hooks/use-lang";

const BASE = API_BASE_URL;

export interface ReportConsideration {
  consideration: string;
  hedge: string;
}

export interface ReportCitation {
  value: number | string;
  source_key: string;
  as_of: string;
}

/** The validated LLM report (one of the 5 surface schemas), served verbatim. */
export interface ReportContent {
  report_type: string;
  schema_version?: number;
  lang?: string;
  headline: string;
  observations: string[];
  considerations: ReportConsideration[];
  disclaimer: string;
  citations?: ReportCitation[];
  // surface-specific extras
  period_days?: number;
  symbol?: string;
  // dashboard recommendation display hints
  confidence?: number | null;
  view_target?: string | null;
}

/** The API response envelope (backend `schemas.reports.ReportResponse`). */
export interface ReportResponse {
  report_type: string;
  content: ReportContent;
  provider: string | null;
  model: string | null;
  verified: boolean;
  created_at: string | null;
}

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
  const { supabase } = await import("@/integrations/supabase/client");
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

function withLang(path: string, lang?: string): string {
  const l = lang ?? getCurrentLang();
  return path + (path.includes("?") ? "&" : "?") + `lang=${l}`;
}

/**
 * Pure URL builder exposed for tests. Joins the API base, the caller's path
 * (already containing any `?query`), and the lang param without mutating order.
 */
export function buildReportUrl(path: string, lang?: string): string {
  return `${BASE}${withLang(path, lang)}`;
}

/** Map an HTTP status to the matching ReportError code. */
function reportErrorForStatus(status: number, path: string): ReportError {
  if (status === 401) return new ReportError("auth", "Session expired", 401);
  if (status === 429) return new ReportError("quota", "Quota exceeded", 429);
  if (status === 503) return new ReportError("unavailable", "Temporarily unavailable", 503);
  return new ReportError("unavailable", `${path}: ${status}`, status);
}

/** POST a user-scoped report endpoint; maps HTTP status to a typed ReportError. */
async function userPostReport(path: string): Promise<ReportResponse> {
  const token = await sessionToken();
  if (!token) throw new ReportError("auth", "Not authenticated");

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: "{}",
    });
  } catch {
    throw new ReportError("network", "Network error");
  }

  if (!res.ok) throw reportErrorForStatus(res.status, path);

  return (await res.json()) as ReportResponse;
}

/** GET a user-scoped report endpoint; same auth + status mapping as the POST helper. */
async function userGetReport(path: string): Promise<ReportResponse> {
  const token = await sessionToken();
  if (!token) throw new ReportError("auth", "Not authenticated");

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new ReportError("network", "Network error");
  }

  if (!res.ok) throw reportErrorForStatus(res.status, path);

  return (await res.json()) as ReportResponse;
}

export function generatePortfolioReport(days = 180, lang?: string): Promise<ReportResponse> {
  return userPostReport(withLang(`/api/ai/report/portfolio?days=${days}`, lang));
}

export function generateFinanceReport(lang?: string): Promise<ReportResponse> {
  return userPostReport(withLang(`/api/ai/report/finance`, lang));
}

/** Daily-cached dashboard nudge. Server returns the latest persisted row. */
export function getDashboardRecommendation(lang?: string): Promise<ReportResponse> {
  return userGetReport(withLang("/api/ai/report/dashboard-recommendation", lang));
}

/** Per-symbol stock analysis. The backend POSTs to stock/{symbol} so we POST. */
export function generateStockReport(symbol: string, lang?: string): Promise<ReportResponse> {
  const upper = symbol.trim().toUpperCase();
  return userPostReport(withLang(`/api/ai/report/stock/${encodeURIComponent(upper)}`, lang));
}

/**
 * The (English) translation key describing a report failure — pass through
 * `t()` at the call site so it localizes and add the key to `lib/lang-ur.ts`.
 */
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
