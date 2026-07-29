// Shared AI DTOs — the backend /api/ai/report/* envelope and its content.
// Mirrors backend schemas/reports.py (served verbatim) and the web app's
// lib/ai/reports-client.ts types, so web and mobile decode one contract.

export interface ReportConsideration {
  consideration: string;
  hedge: string;
}

export interface ReportCitation {
  value: number | string;
  source_key: string;
  as_of: string;
}

export interface ReportMetric {
  label: string;
  value: unknown;
  source_key: string;
  interpretation?: string | null;
}

export interface ReportSection {
  title: string;
  summary: string;
  key_findings?: string[];
  supporting_metrics?: ReportMetric[];
}

export interface ReportActionItem {
  title: string;
  rationale: string;
  timeframe: "now" | "next_30_days" | "next_90_days" | "ongoing";
  priority: "low" | "medium" | "high";
  source_keys?: string[];
}

export interface HoldingReview {
  symbol: string;
  summary: string;
  risk_note?: string | null;
  source_keys?: string[];
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
  executive_summary?: string | null;
  financial_health?: ReportSection | null;
  income_analysis?: ReportSection | null;
  expense_analysis?: ReportSection | null;
  cashflow_analysis?: ReportSection | null;
  savings_analysis?: ReportSection | null;
  budget_analysis?: ReportSection | null;
  goal_progress?: ReportSection | null;
  emergency_fund_review?: ReportSection | null;
  portfolio_health?: ReportSection | null;
  profit_loss_analysis?: ReportSection | null;
  allocation_analysis?: ReportSection | null;
  risk_analysis?: ReportSection | null;
  holdings_analysis?: HoldingReview[];
  action_plan?: ReportActionItem[];
  data_quality_notes?: string[];
  ml_signal_status?: "not_available" | "available";
  ml_signal_note?: string | null;
  // dashboard recommendation display hints
  confidence?: number | null;
  view_target?: string | null;
}

/** The API response envelope (backend schemas.reports.ReportResponse). */
export interface ReportResponse {
  report_type: string;
  content: ReportContent;
  provider: string | null;
  model: string | null;
  verified: boolean;
  created_at: string | null;
}
