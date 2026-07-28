// Typed admin API functions. Thin wrappers over the shared JWT client — every
// call carries the Supabase session token; the backend authorizes server-side.
import { userGet, userPatch, userPost, userPut, userDelete } from "@/lib/psx/client";
import type {
  AdminListItem,
  BugReport,
  ErrorEventRow,
  ErrorGroup,
  TelemetrySummary,
  AdminMe,
  AlertsOverview,
  AuditEntry,
  FlagInfo,
  OverviewResponse,
  Page,
  PlanFeatures,
  PlanUpdate,
  PermissionInfo,
  RoleAssignmentInfo,
  RoleInfo,
  UserDetail,
  UserListItem,
} from "./types";

/** Build a query string, dropping empty/undefined values. */
function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const adminApi = {
  me: () => userGet<AdminMe>("/api/admin/me"),

  overview: () => userGet<OverviewResponse>("/api/admin/overview"),

  listUsers: (params: {
    query?: string;
    status?: string;
    plan?: string;
    sort?: string;
    order?: "asc" | "desc";
    page?: number;
    page_size?: number;
  }) => userGet<Page<UserListItem>>(`/api/admin/users${qs(params)}`),

  getUser: (id: string) => userGet<UserDetail>(`/api/admin/users/${id}`),

  userRoleHistory: (id: string) => userGet<RoleAssignmentInfo[]>(`/api/admin/users/${id}/roles`),

  changeStatus: (id: string, status: string, reason?: string) =>
    userPost(`/api/admin/users/${id}/status`, { status, reason }),

  changeTier: (id: string, plan: string, reason?: string) =>
    userPost(`/api/admin/users/${id}/tier`, { plan, reason }),

  addNote: (id: string, note: string) => userPost(`/api/admin/users/${id}/notes`, { note }),

  assignRole: (id: string, role_slug: string, reason?: string) =>
    userPost(`/api/admin/users/${id}/roles`, { role_slug, reason }),

  revokeRole: (id: string, roleSlug: string) =>
    userDelete(`/api/admin/users/${id}/roles/${roleSlug}`),

  /* --- user lifecycle (Supabase Auth admin API, server-side) --------------
     The password-reset endpoint deliberately returns only a status: the
     recovery URL never leaves the backend. */
  forceSignOut: (id: string) =>
    userPost<{ status: string; detail: string }>(`/api/admin/users/${id}/sign-out`, {}),
  sendPasswordReset: (id: string) =>
    userPost<{ status: string; detail: string }>(`/api/admin/users/${id}/password-reset`, {}),
  resendVerification: (id: string) =>
    userPost<{ status: string; detail: string }>(`/api/admin/users/${id}/resend-verification`, {}),
  anonymiseUser: (id: string, reason?: string) =>
    userPost<{ status: string; detail: string }>(`/api/admin/users/${id}/anonymise`, { reason }),

  /* --- plan entitlements ------------------------------------------------ */
  listPlans: () => userGet<PlanFeatures[]>("/api/admin/plans"),
  updatePlan: (plan: string, changes: PlanUpdate) =>
    userPut<PlanFeatures>(`/api/admin/plans/${plan}`, changes),

  listRoles: () => userGet<RoleInfo[]>("/api/admin/roles"),
  listPermissions: () => userGet<PermissionInfo[]>("/api/admin/permissions"),
  listAdmins: () => userGet<AdminListItem[]>("/api/admin/admins"),

  listFlags: () => userGet<FlagInfo[]>("/api/admin/flags"),
  updateFlag: (key: string, value: unknown, enabled?: boolean, reason?: string) =>
    userPut<FlagInfo>(`/api/admin/flags/${key}`, { value, enabled, reason }),

  listAudit: (params: {
    action?: string;
    /** Restrict to actions performed BY this admin. */
    actor_user_id?: string;
    /** Restrict to actions performed ON this user. */
    target_user_id?: string;
    status?: string;
    /** ISO lower bound on created_at. */
    since?: string;
    /** ISO upper bound on created_at. */
    until?: string;
    page?: number;
    page_size?: number;
  }) => userGet<Page<AuditEntry>>(`/api/admin/audit${qs(params)}`),

  marketData: () => userGet<Record<string, MetricBlockLike>>("/api/admin/market-data"),
  /** Triggers an immediate market-snapshot ingest. Requires market_data.refresh. */
  refreshMarketData: () =>
    userPost<{ status: string; detail: string }>("/api/admin/market-data/refresh", {}),

  signals: () => userGet<Record<string, MetricBlockLike>>("/api/admin/signals"),
  aiOps: () => userGet<Record<string, MetricBlockLike>>("/api/admin/ai"),
  system: () => userGet<SystemHealth>("/api/admin/system"),

  alerts: () => userGet<AlertsOverview>("/api/admin/alerts"),

  /* --- captured errors --------------------------------------------------- */
  errorSummary: () => userGet<TelemetrySummary>("/api/admin/errors/summary"),
  listErrors: (params: {
    query?: string;
    status?: string;
    source?: string;
    since?: string;
    page?: number;
    page_size?: number;
  }) => userGet<Page<ErrorGroup>>(`/api/admin/errors${qs(params)}`),
  getError: (fingerprint: string) =>
    userGet<{ group: ErrorGroup; events: ErrorEventRow[] }>(
      `/api/admin/errors/${encodeURIComponent(fingerprint)}`,
    ),
  triageError: (fingerprint: string, status: string, admin_note?: string) =>
    userPatch<ErrorGroup>(`/api/admin/errors/${encodeURIComponent(fingerprint)}`, {
      status,
      admin_note,
    }),
  userErrors: (userId: string) => userGet<ErrorEventRow[]>(`/api/admin/users/${userId}/errors`),

  /* --- user bug reports -------------------------------------------------- */
  listBugReports: (params: {
    query?: string;
    status?: string;
    category?: string;
    page?: number;
    page_size?: number;
  }) => userGet<Page<BugReport>>(`/api/admin/bug-reports${qs(params)}`),
  triageBugReport: (id: number, status: string, admin_note?: string) =>
    userPatch<BugReport>(`/api/admin/bug-reports/${id}`, { status, admin_note }),
};

export interface MetricBlockLike {
  available: boolean;
  data: Record<string, unknown>;
}

export interface SystemHealth {
  database: { available: boolean };
  deployment: {
    process_role: string;
    scheduler_enabled: boolean;
    environment: string;
  };
}
