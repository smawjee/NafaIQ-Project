// Admin API DTOs — mirror backend app/schemas/admin.py.

export interface AdminMe {
  user_id: string;
  email: string;
  roles: string[];
  permissions: string[];
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface UserListItem {
  id: string;
  email: string | null;
  display_name: string | null;
  plan: string;
  account_status: string;
  created_at: string | null;
  last_sign_in_at: string | null;
}

export interface UserActivity {
  available: boolean;
  counts: Record<string, number>;
}

export interface AdminNote {
  id: number;
  author_id: string | null;
  note: string;
  created_at: string;
}

export interface UserDetail {
  id: string;
  email: string | null;
  display_name: string | null;
  plan: string;
  account_status: string;
  status_reason: string | null;
  status_changed_at: string | null;
  plan_selected_at: string | null;
  created_at: string | null;
  last_sign_in_at: string | null;
  email_confirmed_at: string | null;
  activity: UserActivity;
  roles: string[];
  notes: AdminNote[];
}

export interface RoleAssignmentInfo {
  id: number;
  role_slug: string;
  granted_by: string | null;
  granted_at: string;
  revoked_at: string | null;
  revoked_by: string | null;
  reason: string | null;
}

export interface RoleInfo {
  slug: string;
  name: string;
  description: string | null;
  permissions: string[];
}

export interface PermissionInfo {
  slug: string;
  description: string | null;
}

export interface AdminListItem {
  user_id: string;
  email: string | null;
  roles: string[];
  first_granted_at: string | null;
}

export interface FlagInfo {
  key: string;
  type: "bool" | "int" | "string" | "enum";
  value: unknown;
  allowed: unknown | null;
  enabled: boolean;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface AuditEntry {
  id: number;
  actor_user_id: string | null;
  actor_email: string | null;
  actor_roles: string[];
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  target_user_id: string | null;
  before: unknown | null;
  after: unknown | null;
  reason: string | null;
  request_id: string | null;
  ip: string | null;
  status: string;
  created_at: string;
}

export interface MetricBlock {
  available: boolean;
  data: Record<string, unknown>;
}

export interface OverviewResponse {
  users: MetricBlock;
  tiers: MetricBlock;
  engagement: MetricBlock;
  recent_actions: AuditEntry[];
}

/** GET /api/admin/alerts — platform-wide aggregates, never per-user contents. */
export interface AlertsOverview {
  price_alerts: MetricBlock;
  app_alerts: MetricBlock;
  delivery: MetricBlock;
  events_by_day: MetricBlock;
  top_symbols: MetricBlock;
}

/**
 * A row of `plan_features` — live entitlement configuration, not display copy.
 * Every field is enforced server-side on the request path, so editing one
 * changes what users on that plan can actually do.
 *
 * `plan` and `rank` are read-only: `plan` is the row identity and `rank` orders
 * upgrade comparisons elsewhere in the backend.
 */
export interface PlanFeatures {
  plan: string;
  rank: number;

  max_watchlist: number;
  max_price_alerts: number;
  max_portfolios: number;
  max_holdings_per_portfolio: number;
  max_budgets: number;
  max_bills: number;
  max_goals: number;
  max_finance_history_days: number;

  /** null means "no limit". */
  ai_tutor_daily_limit: number | null;
  ai_reports_per_period: number | null;
  ai_reports_period: "day" | "week" | "month" | null;

  has_email_alerts: boolean;
  has_push_alerts: boolean;
  has_export: boolean;
  has_multi_currency: boolean;
  has_realtime_psx: boolean;
  has_screener_full: boolean;
  has_webhook_integration: boolean;
  has_api_access: boolean;

  description: string | null;
  updated_at: string | null;
}

/** Partial update — only the keys sent are changed. */
export type PlanUpdate = Partial<Omit<PlanFeatures, "plan" | "rank" | "updated_at">> & {
  reason?: string;
};

/** One distinct captured failure. Occurrences roll up into this. */
export interface ErrorGroup {
  fingerprint: string;
  source: "client" | "server";
  message: string;
  route: string | null;
  sample_stack?: string | null;
  status: "open" | "investigating" | "resolved" | "ignored";
  event_count: number;
  users_affected: number;
  first_seen: string;
  last_seen: string;
  admin_note: string | null;
  resolved_at: string | null;
}

export interface ErrorEventRow {
  id: number;
  user_id: string | null;
  user_email: string | null;
  route: string | null;
  stack: string | null;
  status_code: number | null;
  app_version: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface BugReport {
  id: number;
  user_id: string;
  user_email: string | null;
  title: string;
  description: string;
  category: string;
  route: string | null;
  app_version: string | null;
  user_agent: string | null;
  status: "open" | "investigating" | "resolved" | "wont_fix";
  admin_note: string | null;
  error_fingerprint: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface TelemetrySummary {
  errors: { open_groups: number; active_24h: number; events_24h: number };
  reports: { open_reports: number; investigating: number; new_7d: number; total: number };
}
